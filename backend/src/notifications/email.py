import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader

from src.core.config import settings

logger = logging.getLogger(__name__)

_template_dir = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_template_dir)), autoescape=True)

ALLOWED_TEMPLATES = {
    "order_status_changed.html",
    "order_created.html",
    "hibob_sync_complete.html",
}


async def send_email(
    to: str,
    subject: str,
    template_name: str,
    context: dict,
) -> bool:
    if not settings.smtp_host:
        logger.debug("SMTP not configured, skipping email to %s", to)
        return False

    if template_name not in ALLOWED_TEMPLATES:
        logger.error("Blocked email with disallowed template: %s", template_name)
        return False

    try:
        template = _jinja_env.get_template(template_name)
        html_body = template.render(**context)

        message = MIMEMultipart("alternative")
        message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_address))
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(html_body, "html"))

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_use_tls if settings.smtp_port == 587 else False,
            use_tls=settings.smtp_use_tls if settings.smtp_port != 587 else False,
        )
        masked = to.split("@")[0][:2] + "***@" + to.split("@")[-1] if "@" in to else "***"
        logger.info("Email sent to %s: %s", masked, subject)
        return True
    except Exception:
        masked = to.split("@")[0][:2] + "***@" + to.split("@")[-1] if "@" in to else "***"
        logger.exception("Failed to send email to %s", masked)
        return False
