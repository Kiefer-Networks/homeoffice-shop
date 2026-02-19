import logging
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
    "hibob_sync_complete.html",
    "hibob_sync_error.html",
    "role_changed.html",
    "purchase_review_pending.html",
    "delivery_reminder.html",
}


def _get_smtp_config() -> dict:
    host = get_setting("smtp_host")
    port = int(get_setting("smtp_port") or "587")
    use_tls = get_setting("smtp_use_tls").lower() in ("true", "1", "yes")
    return {
        "hostname": host,
        "port": port,
        "username": get_setting("smtp_username") or None,
        "password": get_setting("smtp_password") or None,
        "start_tls": use_tls if port == 587 else False,
        "use_tls": use_tls if port != 587 else False,
    }


async def send_email(
    to: str,
    subject: str,
    template_name: str,
    context: dict,
) -> bool:
    smtp = _get_smtp_config()
    if not smtp["hostname"]:
        logger.debug("SMTP not configured, skipping email to %s", to)
        return False

    if template_name not in ALLOWED_TEMPLATES:
        logger.error("Blocked email with disallowed template: %s", template_name)
        return False

    try:
        # Inject branding context
        context.setdefault("company_name", get_setting("company_name"))
        from src.core.config import settings as app_settings
        context.setdefault("frontend_url", app_settings.frontend_url)

        template = _jinja_env.get_template(template_name)
        html_body = template.render(**context)

        from_name = get_setting("company_name")
        from_address = get_setting("smtp_from_address")

        if "\n" in to or "\r" in to:
            raise ValueError("Invalid email recipient: contains newline characters")

        message = MIMEMultipart("alternative")
        message["From"] = formataddr((from_name, from_address))
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=True)
        domain = from_address.split("@")[-1] if "@" in from_address else "localhost"
        message["Message-ID"] = make_msgid(domain=domain)
        message.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(message, **smtp)
        masked = to.split("@")[0][:2] + "***@" + to.split("@")[-1] if "@" in to else "***"
        logger.info("Email sent to %s: %s", masked, subject)
        return True
    except Exception:
        masked = to.split("@")[0][:2] + "***@" + to.split("@")[-1] if "@" in to else "***"
        logger.exception("Failed to send email to %s", masked)
        return False


async def send_test_email(to: str) -> bool:
    """Send a plain test email to verify SMTP configuration."""
    smtp = _get_smtp_config()
    if not smtp["hostname"]:
        return False

    if "\n" in to or "\r" in to:
        raise ValueError("Invalid email recipient: contains newline characters")

    from_name = get_setting("company_name")
    from_address = get_setting("smtp_from_address")

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

    await aiosmtplib.send(message, **smtp)
    masked = to.split("@")[0][:2] + "***@" + to.split("@")[-1]
    logger.info("Test email sent to %s", masked)
    return True
