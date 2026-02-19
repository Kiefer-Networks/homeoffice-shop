import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import settings
from src.services.settings_service import get_setting

logger = logging.getLogger(__name__)

_SAFE_FILENAME_RE = re.compile(r"^homeoffice_shop_\d{4}-\d{2}-\d{2}(_\d{6})?\.dump$")

_backup_lock = asyncio.Lock()


def _backup_dir() -> Path:
    p = Path(settings.backup_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _enforce_retention() -> None:
    """Delete oldest backups when exceeding retention count."""
    bdir = _backup_dir()
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

        await asyncio.to_thread(filepath.write_bytes, stdout)
        await _enforce_retention()
        logger.info("Backup created: %s (%d bytes, triggered by %s)", filename, len(stdout), triggered_by)
        return filename
