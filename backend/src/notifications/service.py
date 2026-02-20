import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.admin_notification_pref import DEFAULT_EMAIL_EVENTS
from src.notifications.email import send_email
from src.notifications.slack import send_slack_message
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
) -> None:
    staff = await user_repo.get_active_staff(db)
    prefs = await notification_pref_repo.get_all(db)

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

        await send_email(member.email, subject, template_name, context)


async def notify_staff_slack(
    db: AsyncSession,
    *,
    event: str,
    text: str,
    blocks: list[dict] | None = None,
) -> None:
    staff = await user_repo.get_active_staff(db)
    prefs = await notification_pref_repo.get_all(db)

    should_send = any(
        (pref := prefs.get(member.id)) is not None
        and pref.slack_enabled
        and event in (pref.slack_events or [])
        for member in staff
    )

    if not should_send:
        # Default: send if no prefs exist at all
        if not prefs:
            should_send = True

    if should_send:
        await send_slack_message(text, blocks)


async def notify_user_email(
    to: str,
    *,
    subject: str,
    template_name: str,
    context: dict,
) -> None:
    await send_email(to, subject, template_name, context)
