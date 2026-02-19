import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BadRequestError, NotFoundError
from src.services.settings_service import get_setting, update_setting

logger = logging.getLogger(__name__)

SAFE_FILENAME_RE = re.compile(r"^homeoffice_shop_\d{4}-\d{2}-\d{2}(_\d{6})?\.dump$")

_backup_lock = asyncio.Lock()


def backup_dir() -> Path:
    p = Path(settings.backup_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _enforce_retention() -> None:
    """Delete oldest backups when exceeding retention count."""
    bdir = backup_dir()
    dumps = sorted(bdir.glob("homeoffice_shop_*.dump"), key=lambda f: f.stat().st_mtime)
    limit = int(get_setting("backup_max_backups") or str(settings.backup_retention_count))
    limit = max(limit, 1)
    while len(dumps) > limit:
        oldest = dumps.pop(0)
        await asyncio.to_thread(oldest.unlink, missing_ok=True)
        logger.info("Retention: deleted old backup %s", oldest.name)


async def run_backup(triggered_by: str = "scheduler") -> str:
    """Execute pg_dump and store the file. Returns the filename.

    Acquires _backup_lock so only one backup can run at a time.
    Raises RuntimeError if a backup is already in progress or pg_dump fails.
    """
    if _backup_lock.locked():
        raise RuntimeError("A backup is already in progress")

    async with _backup_lock:
        now = datetime.now(timezone.utc)
        filename = f"homeoffice_shop_{now.strftime('%Y-%m-%d_%H%M%S')}.dump"
        filepath = backup_dir() / filename

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

        await asyncio.to_thread(filepath.write_bytes, stdout)
        await _enforce_retention()
        logger.info("Backup created: %s (%d bytes, triggered by %s)", filename, len(stdout), triggered_by)
        return filename


# ── Functions extracted from routes ──────────────────────────────────────────


async def list_backups() -> list[dict]:
    """List all backup files sorted by newest first.

    Returns a list of dicts with filename, size_bytes, and created_at.
    """
    bdir = backup_dir()

    def _sync_list():
        files = sorted(
            bdir.glob("homeoffice_shop_*.dump"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        items = []
        for f in files:
            stat = f.stat()
            items.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })
        return items

    return await asyncio.to_thread(_sync_list)


async def get_backup_path(filename: str) -> Path:
    """Validate filename and return the full path.

    Raises BadRequestError for invalid filenames.
    Raises NotFoundError if the file does not exist.
    """
    if not SAFE_FILENAME_RE.match(filename):
        raise BadRequestError("Invalid filename")

    filepath = backup_dir() / filename
    if not await asyncio.to_thread(filepath.is_file):
        raise NotFoundError("Backup not found")

    return filepath


async def delete_backup(filename: str) -> None:
    """Validate and delete a backup file.

    Raises BadRequestError for invalid filenames.
    Raises NotFoundError if the file does not exist.
    """
    if not SAFE_FILENAME_RE.match(filename):
        raise BadRequestError("Invalid filename")

    filepath = backup_dir() / filename
    if not await asyncio.to_thread(filepath.is_file):
        raise NotFoundError("Backup not found")

    await asyncio.to_thread(filepath.unlink)


async def get_schedule() -> dict:
    """Read backup schedule from settings and return as a dict."""
    return {
        "enabled": get_setting("backup_schedule_enabled") == "true",
        "frequency": get_setting("backup_schedule_frequency") or "daily",
        "hour": int(get_setting("backup_schedule_hour") or "2"),
        "minute": int(get_setting("backup_schedule_minute") or "0"),
        "weekday": int(get_setting("backup_schedule_weekday") or "0"),
        "max_backups": int(
            get_setting("backup_max_backups") or str(settings.backup_retention_count)
        ),
    }


async def update_schedule(
    db: AsyncSession,
    *,
    enabled: bool | None = None,
    frequency: str | None = None,
    hour: int | None = None,
    minute: int | None = None,
    weekday: int | None = None,
    max_backups: int | None = None,
    updated_by: UUID | None = None,
) -> dict:
    """Update backup schedule settings and return the new schedule."""
    VALID_FREQUENCIES = ("hourly", "daily", "weekly")
    if frequency is not None and frequency not in VALID_FREQUENCIES:
        raise BadRequestError(f"Invalid frequency: must be one of {VALID_FREQUENCIES}")

    if enabled is not None:
        await update_setting(
            db, "backup_schedule_enabled", str(enabled).lower(), updated_by=updated_by,
        )
    if frequency is not None:
        await update_setting(
            db, "backup_schedule_frequency", frequency, updated_by=updated_by,
        )
    if hour is not None:
        await update_setting(
            db, "backup_schedule_hour", str(hour), updated_by=updated_by,
        )
    if minute is not None:
        await update_setting(
            db, "backup_schedule_minute", str(minute), updated_by=updated_by,
        )
    if weekday is not None:
        await update_setting(
            db, "backup_schedule_weekday", str(weekday), updated_by=updated_by,
        )
    if max_backups is not None:
        await update_setting(
            db, "backup_max_backups", str(max_backups), updated_by=updated_by,
        )

    return await get_schedule()
