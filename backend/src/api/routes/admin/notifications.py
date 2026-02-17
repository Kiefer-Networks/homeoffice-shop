from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.models.dto.notification import NotificationPrefUpdate
from src.models.orm.user import User
from src.repositories import notification_pref_repo

router = APIRouter(prefix="/notifications", tags=["admin-notifications"])

VALID_SLACK_EVENTS = {
    "order.created",
    "order.status_changed",
    "order.cancelled",
    "hibob.sync",
    "price.refresh",
}

VALID_EMAIL_EVENTS = {
    "order.created",
}


@router.get("/preferences")
async def get_my_preferences(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    pref = await notification_pref_repo.get_by_user_id(db, admin.id)
    if not pref:
        return {
            "slack_enabled": True,
            "slack_events": ["order.created", "order.cancelled", "hibob.sync"],
            "email_enabled": True,
            "email_events": ["order.created"],
        }
    return pref


@router.put("/preferences")
async def update_my_preferences(
    body: NotificationPrefUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    kwargs = {}
    if body.slack_enabled is not None:
        kwargs["slack_enabled"] = body.slack_enabled
    if body.slack_events is not None:
        kwargs["slack_events"] = [e for e in body.slack_events if e in VALID_SLACK_EVENTS]
    if body.email_enabled is not None:
        kwargs["email_enabled"] = body.email_enabled
    if body.email_events is not None:
        kwargs["email_events"] = [e for e in body.email_events if e in VALID_EMAIL_EVENTS]

    pref = await notification_pref_repo.upsert(db, admin.id, **kwargs)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.notification_prefs.updated",
        resource_type="notification_pref",
        details=kwargs, ip_address=ip,
    )

    return pref
