import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import log_admin_action
from src.core.exceptions import BadRequestError
from src.models.dto import DetailResponse
from src.models.dto.settings import AppSettingResponse, AppSettingUpdate, AppSettingsResponse, TestEmailRequest
from src.models.orm.user import User
from src.notifications.email import mask_email, send_test_email
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

    SENSITIVE_KEYS = {"smtp_password", "slack_webhook_url"}

    # Skip update if the value is the redaction marker (password not changed)
    if key in SENSITIVE_KEYS and body.value == "********":
        return {"key": key, "value": "********"}

    old_value = settings_service.get_setting(key)
    masked = key in SENSITIVE_KEYS
    display_old = "********" if masked else old_value
    display_new = "********" if masked else body.value

    await settings_service.update_setting(db, key, body.value, admin.id)

    await log_admin_action(
        db, request, admin.id, "admin.settings.updated",
        resource_type="app_setting",
        details={
            "key": key,
            "old_value": display_old,
            "new_value": display_new,
        },
    )

    value = body.value
    if key in SENSITIVE_KEYS:
        value = "********"
    return {"key": key, "value": value}


@router.post("/test-email", response_model=DetailResponse)
async def test_email(
    body: TestEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    await log_admin_action(
        db, request, admin.id, "admin.settings.test_email",
        resource_type="app_setting",
        details={"to": body.to},
    )

    try:
        result = await send_test_email(body.to)
        if not result:
            raise BadRequestError("SMTP is not configured. Please set SMTP host first.")
        return {"detail": "Test email sent successfully"}
    except BadRequestError:
        raise
    except Exception:
        logger.exception("Failed to send test email to %s", mask_email(body.to))
        raise BadRequestError("Failed to send test email. Check SMTP configuration.")
