import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.api.dependencies.rate_limit import rate_limit
from src.audit.service import write_audit_log
from src.core.config import settings
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.orm.user import User
from src.services.settings_service import get_setting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["admin-backup"])

_backup_lock = asyncio.Lock()

_SAFE_FILENAME_RE = re.compile(r"^homeoffice_shop_\d{4}-\d{2}-\d{2}(_\d{6})?\.dump$")


def _backup_dir() -> Path:
    p = Path(settings.backup_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _enforce_retention() -> None:
    """Delete oldest backups when exceeding retention count."""
    bdir = _backup_dir()
    dumps = sorted(bdir.glob("homeoffice_shop_*.dump"), key=lambda f: f.stat().st_mtime)
    limit = max(settings.backup_retention_count, 1)
    while len(dumps) > limit:
        oldest = dumps.pop(0)
        oldest.unlink(missing_ok=True)
        logger.info("Retention: deleted old backup %s", oldest.name)


async def run_backup(triggered_by: str = "scheduler") -> str:
    """Execute pg_dump and store the file. Returns the filename."""
    now = datetime.now(timezone.utc)
    filename = f"homeoffice_shop_{now.strftime('%Y-%m-%d_%H%M%S')}.dump"
    filepath = _backup_dir() / filename

    env = {**os.environ, "PGPASSWORD": settings.db_password}

    process = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-h", settings.db_host,
        "-p", str(settings.db_port),
        "-U", settings.db_user,
        "-Fc",
        settings.db_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error("pg_dump failed (exit %d): %s", process.returncode, stderr.decode())
        raise RuntimeError("pg_dump failed")

    filepath.write_bytes(stdout)
    _enforce_retention()
    logger.info("Backup created: %s (%d bytes, triggered by %s)", filename, len(stdout), triggered_by)
    return filename


@router.post(
    "/export",
    dependencies=[rate_limit(limit=5, window_seconds=3600, key_prefix="backup")],
)
async def export_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if _backup_lock.locked():
        raise BadRequestError("A backup is already in progress")

    async with _backup_lock:
        try:
            filename = await run_backup(triggered_by=str(admin.id))
        except RuntimeError:
            raise BadRequestError("Database backup failed")

        filepath = _backup_dir() / filename
        size = filepath.stat().st_size

        ip = request.client.host if request.client else None
        await write_audit_log(
            db, user_id=admin.id, action="admin.backup.exported",
            resource_type="database",
            details={"filename": filename, "size_bytes": size},
            ip_address=ip,
        )

        return FileResponse(
            path=str(filepath),
            media_type="application/octet-stream",
            filename=filename,
        )


@router.get("/list")
async def list_backups(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    bdir = _backup_dir()
    files = sorted(bdir.glob("homeoffice_shop_*.dump"), key=lambda f: f.stat().st_mtime, reverse=True)
    items = []
    for f in files:
        stat = f.stat()
        items.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return {"items": items}


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


@router.delete("/{filename}")
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

    filepath.unlink()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.backup.deleted",
        resource_type="database",
        details={"filename": filename},
        ip_address=ip,
    )

    return {"detail": "Backup deleted"}


@router.get("/schedule")
async def get_schedule(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return {
        "enabled": get_setting("backup_schedule_enabled") == "true",
        "hour": int(get_setting("backup_schedule_hour") or "2"),
        "minute": int(get_setting("backup_schedule_minute") or "0"),
    }


@router.put("/schedule")
async def update_schedule(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    body = await request.json()
    enabled = body.get("enabled")
    hour = body.get("hour")
    minute = body.get("minute")

    if enabled is not None:
        if not isinstance(enabled, bool):
            raise BadRequestError("enabled must be a boolean")

    if hour is not None:
        if not isinstance(hour, int) or not (0 <= hour <= 23):
            raise BadRequestError("hour must be 0-23")

    if minute is not None:
        if not isinstance(minute, int) or not (0 <= minute <= 59):
            raise BadRequestError("minute must be 0-59")

    from src.services.settings_service import update_setting

    if enabled is not None:
        await update_setting(db, "backup_schedule_enabled", str(enabled).lower(), updated_by=admin.id)
    if hour is not None:
        await update_setting(db, "backup_schedule_hour", str(hour), updated_by=admin.id)
    if minute is not None:
        await update_setting(db, "backup_schedule_minute", str(minute), updated_by=admin.id)
    await db.commit()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.backup.schedule_updated",
        resource_type="database",
        details={"enabled": enabled, "hour": hour, "minute": minute},
        ip_address=ip,
    )

    return await get_schedule(db=db, admin=admin)
