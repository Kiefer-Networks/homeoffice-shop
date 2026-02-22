import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.admin_notification_pref import DEFAULT_EMAIL_EVENTS
from src.notifications.email import send_email
from src.repositories import user_repo, notification_pref_repo

logger = logging.getLogger(__name__)

ADMIN_ONLY_EVENTS = {"hibob.sync", "hibob.sync_error", "price.refresh", "hibob.purchase_review"}


async def notify_staff_email(
    db: AsyncSession,
    *,
    event: str,
    subject: str,
    template_name: str,
    context: dict,
) -> int:
    """Send an email to all eligible staff members. Returns the number of emails sent."""
    staff = await user_repo.get_active_staff(db)
    prefs = await notification_pref_repo.get_all(db)

    recipients: list[str] = []
    for member in staff:
        pref = prefs.get(member.id)

        if not pref:
            # No prefs row: apply model defaults and skip admin-only for managers
            if member.role == "manager" and event in ADMIN_ONLY_EVENTS:
                continue
            if event not in DEFAULT_EMAIL_EVENTS:
                continue
        else:
            if not pref.email_enabled:
                continue
            if event not in (pref.email_events or []):
                continue

        recipients.append(member.email)

    if not recipients:
        return 0

    results = await asyncio.gather(
        *(send_email(addr, subject, template_name, context) for addr in recipients)
    )
    return sum(1 for r in results if r is True)


async def notify_user_email(
    to: str,
    *,
    subject: str,
    template_name: str,
    context: dict,
) -> bool:
    """Send an email to a single user. Returns True if the email was sent."""
    return await send_email(to, subject, template_name, context)
