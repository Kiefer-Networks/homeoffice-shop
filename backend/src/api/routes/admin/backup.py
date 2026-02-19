import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.api.dependencies.rate_limit import rate_limit
from src.audit.service import audit_context, write_audit_log
from src.core.config import settings
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.dto.backup import (
    BackupFileResponse,
    BackupListResponse,
    BackupScheduleResponse,
    BackupScheduleUpdate,
)
from src.models.orm.user import User
from src.services.backup_service import _backup_dir, _SAFE_FILENAME_RE, run_backup
from src.services.settings_service import get_setting, update_setting

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
        filename = await run_backup(triggered_by=str(admin.id))
    except RuntimeError as exc:
        raise BadRequestError(str(exc))

    filepath = _backup_dir() / filename
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
    bdir = _backup_dir()
    files = sorted(bdir.glob("homeoffice_shop_*.dump"), key=lambda f: f.stat().st_mtime, reverse=True)
    items = []
    for f in files:
        stat = f.stat()
        items.append(BackupFileResponse(
            filename=f.name,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        ))
    return BackupListResponse(items=items)


@router.get("/download/{filename}")
async def download_backup(
    filename: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if not _SAFE_FILENAME_RE.match(filename):
        raise BadRequestError("Invalid filename")

    filepath = _backup_dir() / filename
    if not filepath.is_file():
        raise NotFoundError("Backup not found")

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
    if not _SAFE_FILENAME_RE.match(filename):
        raise BadRequestError("Invalid filename")

    filepath = _backup_dir() / filename
    if not filepath.is_file():
        raise NotFoundError("Backup not found")

    await asyncio.to_thread(filepath.unlink)

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
    return BackupScheduleResponse(
        enabled=get_setting("backup_schedule_enabled") == "true",
        frequency=get_setting("backup_schedule_frequency") or "daily",
        hour=int(get_setting("backup_schedule_hour") or "2"),
        minute=int(get_setting("backup_schedule_minute") or "0"),
        weekday=int(get_setting("backup_schedule_weekday") or "0"),
        max_backups=int(get_setting("backup_max_backups") or str(settings.backup_retention_count)),
    )


@router.put("/schedule", response_model=BackupScheduleResponse)
async def update_schedule(
    body: BackupScheduleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if body.enabled is not None:
        await update_setting(db, "backup_schedule_enabled", str(body.enabled).lower(), updated_by=admin.id)
    if body.frequency is not None:
        await update_setting(db, "backup_schedule_frequency", body.frequency, updated_by=admin.id)
    if body.hour is not None:
        await update_setting(db, "backup_schedule_hour", str(body.hour), updated_by=admin.id)
    if body.minute is not None:
        await update_setting(db, "backup_schedule_minute", str(body.minute), updated_by=admin.id)
    if body.weekday is not None:
        await update_setting(db, "backup_schedule_weekday", str(body.weekday), updated_by=admin.id)
    if body.max_backups is not None:
        await update_setting(db, "backup_max_backups", str(body.max_backups), updated_by=admin.id)

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

    return await get_schedule(db=db, admin=admin)
