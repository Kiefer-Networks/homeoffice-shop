from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import BadRequestError
from src.models.dto.settings import AppSettingResponse, AppSettingUpdate, AppSettingsResponse
from src.models.orm.user import User
from src.services import settings_service

router = APIRouter(prefix="/settings", tags=["admin-settings"])


@router.get("", response_model=AppSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    settings = await settings_service.get_all_settings(db)
    return {"settings": settings}


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

    old_value = settings_service.get_setting(key)
    await settings_service.update_setting(db, key, body.value, admin.id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.settings.updated",
        resource_type="app_setting",
        details={"key": key, "old_value": old_value, "new_value": body.value},
        ip_address=ip,
    )

    return {"key": key, "value": body.value}
