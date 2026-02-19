from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.models.dto.notification import NotificationPrefResponse, NotificationPrefUpdate
from src.models.orm.user import User
from src.services import notification_service

router = APIRouter(prefix="/notifications", tags=["admin-notifications"])


@router.get("/preferences", response_model=NotificationPrefResponse)
async def get_my_preferences(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_staff),
):
    return await notification_service.get_preferences(db, user.id, user.role)


@router.put("/preferences", response_model=NotificationPrefResponse)
async def update_my_preferences(
    body: NotificationPrefUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_staff),
):
    result = await notification_service.update_preferences(
        db, user.id, user.role,
        slack_enabled=body.slack_enabled,
        slack_events=body.slack_events,
        email_enabled=body.email_enabled,
        email_events=body.email_events,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=user.id, action="admin.notification_prefs.updated",
        resource_type="notification_pref",
        details={
            k: v for k, v in {
                "slack_enabled": body.slack_enabled,
                "slack_events": body.slack_events,
                "email_enabled": body.email_enabled,
                "email_events": body.email_events,
            }.items() if v is not None
        },
        ip_address=ip, user_agent=ua,
    )

    return result
