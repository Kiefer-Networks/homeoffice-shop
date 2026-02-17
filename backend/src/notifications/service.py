import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.notifications.email import send_email
from src.notifications.slack import send_slack_message
from src.repositories import user_repo, notification_pref_repo

logger = logging.getLogger(__name__)


async def notify_admins_email(
    db: AsyncSession,
    *,
    event: str,
    subject: str,
    template_name: str,
    context: dict,
) -> None:
    admins = await user_repo.get_active_admins(db)
    prefs = await notification_pref_repo.get_all(db)

    for admin in admins:
        pref = prefs.get(admin.id)
        if pref and not pref.email_enabled:
            continue
        if pref and event not in (pref.email_events or []):
            continue

        await send_email(admin.email, subject, template_name, context)


async def notify_admins_slack(
    db: AsyncSession,
    *,
    event: str,
    text: str,
    blocks: list[dict] | None = None,
) -> None:
    admins = await user_repo.get_active_admins(db)
    prefs = await notification_pref_repo.get_all(db)

    should_send = any(
        (pref := prefs.get(admin.id)) is not None
        and pref.slack_enabled
        and event in (pref.slack_events or [])
        for admin in admins
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
