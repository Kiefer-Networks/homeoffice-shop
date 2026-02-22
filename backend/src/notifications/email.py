import asyncio
import logging
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader

from src.services.settings_service import get_setting

logger = logging.getLogger(__name__)

_template_dir = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_template_dir)), autoescape=True)

ALLOWED_TEMPLATES = {
    "order_status_changed.html",
    "order_created.html",
    "order_cancelled.html",
    "order_tracking_update.html",
    "hibob_sync_complete.html",
    "hibob_sync_error.html",
    "role_changed.html",
    "purchase_review_pending.html",
    "delivery_reminder.html",
    "welcome.html",
    "budget_adjusted.html",
}

_RETRY_DELAYS = (1, 2, 4)

_TRANSIENT_EXCEPTIONS = (
    aiosmtplib.SMTPConnectError,
    aiosmtplib.SMTPConnectTimeoutError,
    aiosmtplib.SMTPServerDisconnected,
)


def _is_placeholder_address(address: str | None) -> bool:
    """Return True if the from-address is empty or contains a placeholder domain."""
    if not address or not address.strip():
        return True
    return "your-company.com" in address


def _sanitize_header(value: str) -> str:
    """Strip newline characters to prevent email header injection."""
    return value.replace("\r", "").replace("\n", "")


def _html_to_plaintext(html_body: str) -> str:
    """Convert HTML to plaintext for the email alternative part."""
    text = re.sub(r"<br\s*/?>", "\n", html_body)
    text = re.sub(r"</(?:p|div|tr|li|h[1-6])>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def mask_email(address: str) -> str:
    """Mask an email address for safe logging (exported for use in other modules)."""
    if "@" in address:
        return address.split("@")[0][:2] + "***@" + address.split("@")[-1]
    return "***"


async def _send_with_retry(message: MIMEMultipart, smtp: dict) -> None:
    """Send an email message with retry on transient SMTP errors."""
    last_exc: Exception | None = None
    for attempt, delay in enumerate(_RETRY_DELAYS, 1):
        try:
            await aiosmtplib.send(message, **smtp)
            return
        except aiosmtplib.SMTPResponseException as exc:
            if exc.code >= 500:
                raise
            logger.warning("Transient SMTP error (attempt %d/%d): %s", attempt, len(_RETRY_DELAYS), exc)
            last_exc = exc
        except _TRANSIENT_EXCEPTIONS as exc:
            logger.warning("Transient SMTP error (attempt %d/%d): %s", attempt, len(_RETRY_DELAYS), exc)
            last_exc = exc
        if attempt < len(_RETRY_DELAYS):
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


_SMTP_TIMEOUT_SECONDS = 30

def _get_smtp_config() -> dict:
    host = get_setting("smtp_host")
    port = int(get_setting("smtp_port") or "587")
    use_tls = get_setting("smtp_use_tls").lower() in ("true", "1", "yes")
    return {
        "hostname": host,
        "port": port,
        "username": get_setting("smtp_username") or None,
        "password": get_setting("smtp_password") or None,
        "start_tls": use_tls and port != 465,
        "use_tls": port == 465,
        "timeout": _SMTP_TIMEOUT_SECONDS,
    }


async def send_email(
    to: str,
    subject: str,
    template_name: str,
    context: dict,
) -> bool:
    smtp = _get_smtp_config()
    if not smtp["hostname"]:
        logger.debug("SMTP not configured, skipping email to %s", mask_email(to))
        return False

    if template_name not in ALLOWED_TEMPLATES:
        logger.error("Blocked email with disallowed template: %s", template_name)
        return False

    from_address = get_setting("smtp_from_address")
    if _is_placeholder_address(from_address):
        logger.warning("SMTP from-address is a placeholder (%s), skipping email", from_address)
        return False

    try:
        # Inject branding context
        context.setdefault("company_name", get_setting("company_name"))
        from src.core.config import settings as app_settings
        context.setdefault("frontend_url", app_settings.frontend_url)

        template = _jinja_env.get_template(template_name)
        html_body = template.render(**context)

        from_name = _sanitize_header(get_setting("company_name"))
        subject = _sanitize_header(subject)

        if "\n" in to or "\r" in to:
            raise ValueError("Invalid email recipient: contains newline characters")

        message = MIMEMultipart("alternative")
        message["From"] = formataddr((from_name, from_address))
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        domain = from_address.split("@")[-1] if "@" in from_address else "localhost"
        message["Message-ID"] = make_msgid(domain=domain)
        message.attach(MIMEText(_html_to_plaintext(html_body), "plain"))
        message.attach(MIMEText(html_body, "html"))

        await _send_with_retry(message, smtp)
        masked = mask_email(to)
        logger.info("Email sent to %s: %s", masked, subject)
        return True
    except Exception:
        masked = mask_email(to)
        logger.exception("Failed to send email to %s", masked)
        return False


async def send_test_email(to: str) -> bool:
    """Send a plain test email to verify SMTP configuration."""
    smtp = _get_smtp_config()
    if not smtp["hostname"]:
        return False

    from_address = get_setting("smtp_from_address")
    if _is_placeholder_address(from_address):
        logger.warning("SMTP from-address is a placeholder (%s), skipping test email", from_address)
        return False

    if "\n" in to or "\r" in to:
        raise ValueError("Invalid email recipient: contains newline characters")

    from_name = _sanitize_header(get_setting("company_name"))

    message = MIMEMultipart("alternative")
    message["From"] = formataddr((from_name, from_address))
    message["To"] = to
    message["Subject"] = "Test Email - Home Office Shop"
    message["Date"] = formatdate(localtime=True)
    domain = from_address.split("@")[-1] if "@" in from_address else "localhost"
    message["Message-ID"] = make_msgid(domain=domain)
    message.attach(MIMEText(
        "<h2>SMTP Test</h2><p>SMTP configuration is working correctly.</p>",
        "html",
    ))

    await _send_with_retry(message, smtp)
    masked = mask_email(to)
    logger.info("Test email sent to %s", masked)
    return True
