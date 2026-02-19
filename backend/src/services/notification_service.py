import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import notification_pref_repo

logger = logging.getLogger(__name__)

ADMIN_ONLY_EVENTS = {"hibob.sync", "hibob.sync_error", "price.refresh", "hibob.purchase_review"}
ORDER_EVENTS = {"order.created", "order.status_changed", "order.cancelled"}

ALL_SLACK_EVENTS = ORDER_EVENTS | ADMIN_ONLY_EVENTS
ALL_EMAIL_EVENTS = ORDER_EVENTS | {"hibob.sync_error", "hibob.purchase_review"}


def allowed_events(role: str, channel_events: set[str]) -> set[str]:
    """Return the set of events a given role may subscribe to."""
    if role == "admin":
        return channel_events
    return channel_events - ADMIN_ONLY_EVENTS


def _default_preferences(role: str) -> dict:
    """Build the default preference response when no DB record exists."""
    return {
        "slack_enabled": True,
        "slack_events": ["order.created", "order.cancelled"],
        "email_enabled": True,
        "email_events": ["order.created"],
        "available_slack_events": sorted(allowed_events(role, ALL_SLACK_EVENTS)),
        "available_email_events": sorted(allowed_events(role, ALL_EMAIL_EVENTS)),
    }


async def get_preferences(db: AsyncSession, user_id: UUID, role: str) -> dict:
    """Return notification preferences for a user, with defaults if none stored."""
    pref = await notification_pref_repo.get_by_user_id(db, user_id)
    allowed_slack = sorted(allowed_events(role, ALL_SLACK_EVENTS))
    allowed_email = sorted(allowed_events(role, ALL_EMAIL_EVENTS))

    if not pref:
        return _default_preferences(role)

    return {
        "id": pref.id,
        "user_id": pref.user_id,
        "slack_enabled": pref.slack_enabled,
        "slack_events": pref.slack_events,
        "email_enabled": pref.email_enabled,
        "email_events": pref.email_events,
        "available_slack_events": allowed_slack,
        "available_email_events": allowed_email,
    }


async def update_preferences(
    db: AsyncSession,
    user_id: UUID,
    role: str,
    *,
    slack_enabled: bool | None = None,
    slack_events: list[str] | None = None,
    email_enabled: bool | None = None,
    email_events: list[str] | None = None,
) -> dict:
    """Validate and persist notification preference updates.

    Filters events against the user's role-allowed set before saving.
    Returns the full preference response dict.
    """
    allowed_slack = allowed_events(role, ALL_SLACK_EVENTS)
    allowed_email = allowed_events(role, ALL_EMAIL_EVENTS)

    kwargs: dict = {}
    if slack_enabled is not None:
        kwargs["slack_enabled"] = slack_enabled
    if slack_events is not None:
        kwargs["slack_events"] = [e for e in slack_events if e in allowed_slack]
    if email_enabled is not None:
        kwargs["email_enabled"] = email_enabled
    if email_events is not None:
        kwargs["email_events"] = [e for e in email_events if e in allowed_email]

    pref = await notification_pref_repo.upsert(db, user_id, **kwargs)

    return {
        "id": pref.id,
        "user_id": pref.user_id,
        "slack_enabled": pref.slack_enabled,
        "slack_events": pref.slack_events,
        "email_enabled": pref.email_enabled,
        "email_events": pref.email_events,
        "available_slack_events": sorted(allowed_slack),
        "available_email_events": sorted(allowed_email),
    }
