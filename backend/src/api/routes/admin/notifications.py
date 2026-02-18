from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.models.dto.notification import NotificationPrefUpdate
from src.models.orm.user import User
from src.repositories import notification_pref_repo

router = APIRouter(prefix="/notifications", tags=["admin-notifications"])

ADMIN_ONLY_EVENTS = {"hibob.sync", "price.refresh"}
ORDER_EVENTS = {"order.created", "order.status_changed", "order.cancelled"}

ALL_SLACK_EVENTS = ORDER_EVENTS | ADMIN_ONLY_EVENTS
ALL_EMAIL_EVENTS = ORDER_EVENTS


def _allowed_events(role: str, channel_events: set[str]) -> set[str]:
    if role == "admin":
        return channel_events
    return channel_events - ADMIN_ONLY_EVENTS


@router.get("/preferences")
async def get_my_preferences(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_staff),
):
    pref = await notification_pref_repo.get_by_user_id(db, user.id)
    allowed_slack = sorted(_allowed_events(user.role, ALL_SLACK_EVENTS))
    allowed_email = sorted(_allowed_events(user.role, ALL_EMAIL_EVENTS))

    if not pref:
        return {
            "slack_enabled": True,
            "slack_events": ["order.created", "order.cancelled"],
            "email_enabled": True,
            "email_events": ["order.created"],
            "available_slack_events": allowed_slack,
            "available_email_events": allowed_email,
        }
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


@router.put("/preferences")
async def update_my_preferences(
    body: NotificationPrefUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_staff),
):
    allowed_slack = _allowed_events(user.role, ALL_SLACK_EVENTS)
    allowed_email = _allowed_events(user.role, ALL_EMAIL_EVENTS)

    kwargs = {}
    if body.slack_enabled is not None:
        kwargs["slack_enabled"] = body.slack_enabled
    if body.slack_events is not None:
        kwargs["slack_events"] = [e for e in body.slack_events if e in allowed_slack]
    if body.email_enabled is not None:
        kwargs["email_enabled"] = body.email_enabled
    if body.email_events is not None:
        kwargs["email_events"] = [e for e in body.email_events if e in allowed_email]

    pref = await notification_pref_repo.upsert(db, user.id, **kwargs)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=user.id, action="admin.notification_prefs.updated",
        resource_type="notification_pref",
        details=kwargs, ip_address=ip,
    )

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
