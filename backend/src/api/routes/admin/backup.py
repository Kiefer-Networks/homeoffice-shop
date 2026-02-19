import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.api.dependencies.rate_limit import rate_limit
from src.audit.service import audit_context, write_audit_log
from src.core.exceptions import BadRequestError
from src.models.dto.backup import (
    BackupFileResponse,
    BackupListResponse,
    BackupScheduleResponse,
    BackupScheduleUpdate,
)
from src.models.orm.user import User
from src.services import backup_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["admin-backup"])


@router.post(
    "/export",
    dependencies=[rate_limit(limit=5, window_seconds=3600, key_prefix="backup")],
)
async def export_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        filename = await backup_service.run_backup(triggered_by=str(admin.id))
    except RuntimeError as exc:
        raise BadRequestError(str(exc))

    filepath = await backup_service.get_backup_path(filename)
    size = filepath.stat().st_size

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.backup.exported",
        resource_type="database",
        details={"filename": filename, "size_bytes": size},
        ip_address=ip, user_agent=ua,
    )

    return FileResponse(
        path=str(filepath),
        media_type="application/octet-stream",
        filename=filename,
    )


@router.get("/list", response_model=BackupListResponse)
async def list_backups(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    items = await backup_service.list_backups()
    return BackupListResponse(
        items=[BackupFileResponse(**item) for item in items],
    )


@router.get("/download/{filename}")
async def download_backup(
    filename: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    filepath = await backup_service.get_backup_path(filename)

    return FileResponse(
        path=str(filepath),
        media_type="application/octet-stream",
        filename=filename,
    )


@router.delete("/{filename}", status_code=204)
async def delete_backup(
    filename: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    await backup_service.delete_backup(filename)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.backup.deleted",
        resource_type="database",
        details={"filename": filename},
        ip_address=ip, user_agent=ua,
    )

    return Response(status_code=204)


@router.get("/schedule", response_model=BackupScheduleResponse)
async def get_schedule(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    schedule = await backup_service.get_schedule()
    return BackupScheduleResponse(**schedule)


@router.put("/schedule", response_model=BackupScheduleResponse)
async def update_schedule(
    body: BackupScheduleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    schedule = await backup_service.update_schedule(
        db,
        enabled=body.enabled,
        frequency=body.frequency,
        hour=body.hour,
        minute=body.minute,
        weekday=body.weekday,
        max_backups=body.max_backups,
        updated_by=admin.id,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.backup.schedule_updated",
        resource_type="database",
        details={
            "enabled": body.enabled, "frequency": body.frequency,
            "hour": body.hour, "minute": body.minute, "weekday": body.weekday,
            "max_backups": body.max_backups,
        },
        ip_address=ip, user_agent=ua,
    )

    return BackupScheduleResponse(**schedule)
