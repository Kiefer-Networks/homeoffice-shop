import asyncio
import logging
import os
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.api.dependencies.rate_limit import rate_limit
from src.audit.service import write_audit_log
from src.core.config import settings
from src.core.exceptions import BadRequestError
from src.models.orm.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["admin-backup"])

_backup_lock = asyncio.Lock()


@router.post(
    "/export",
    dependencies=[rate_limit(limit=2, window_seconds=3600, key_prefix="backup")],
)
async def export_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if _backup_lock.locked():
        raise BadRequestError("A backup is already in progress")

    async with _backup_lock:
        filename = f"homeoffice_shop_{date.today().isoformat()}.dump"

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
            raise BadRequestError("Database backup failed")

        ip = request.client.host if request.client else None
        await write_audit_log(
            db, user_id=admin.id, action="admin.backup.exported",
            resource_type="database",
            details={"filename": filename, "size_bytes": len(stdout)},
            ip_address=ip,
        )

        return Response(
            content=stdout,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
