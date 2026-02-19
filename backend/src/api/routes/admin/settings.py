import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.core.exceptions import BadRequestError
from src.models.dto import DetailResponse
from src.models.dto.settings import AppSettingResponse, AppSettingUpdate, AppSettingsResponse, TestEmailRequest
from src.models.orm.user import User
from src.notifications.email import send_test_email
from src.services import settings_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["admin-settings"])


@router.get("", response_model=AppSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    all_settings = await settings_service.get_all_settings_redacted(db)
    return {"settings": all_settings}


@router.put("/{key}", response_model=AppSettingResponse)
async def update_setting(
    key: str,
    body: AppSettingUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if key not in settings_service.DEFAULT_SETTINGS:
        raise BadRequestError(f"Unknown setting key: {key}")

    # Skip update if the value is the redaction marker (password not changed)
    if key == "smtp_password" and body.value == "********":
        return {"key": key, "value": "********"}

    old_value = settings_service.get_setting(key)
    await settings_service.update_setting(db, key, body.value, admin.id)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.settings.updated",
        resource_type="app_setting",
        details={
            "key": key,
            "old_value": "********" if key == "smtp_password" else old_value,
            "new_value": "********" if key == "smtp_password" else body.value,
        },
        ip_address=ip, user_agent=ua,
    )

    return {"key": key, "value": body.value}


@router.post("/test-email", response_model=DetailResponse)
async def test_email(
    body: TestEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.settings.test_email",
        resource_type="app_setting",
        details={"to": body.to},
        ip_address=ip, user_agent=ua,
    )

    try:
        result = await send_test_email(body.to)
        if not result:
            raise BadRequestError("SMTP is not configured. Please set SMTP host first.")
        return {"detail": "Test email sent successfully"}
    except BadRequestError:
        raise
    except Exception:
        logger.exception("Failed to send test email to %s", body.to)
        raise BadRequestError("Failed to send test email. Check SMTP configuration.")
