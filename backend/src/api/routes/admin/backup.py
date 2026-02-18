import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.config import settings
from src.models.orm.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["admin-backup"])


@router.post("/export")
async def export_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    filename = f"homeoffice_shop_{date.today().isoformat()}.dump"

    process = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-h", settings.db_host,
        "-p", str(settings.db_port),
        "-U", settings.db_user,
        "-Fc",
        settings.db_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"PGPASSWORD": settings.db_password},
    )

    async def stream_output():
        assert process.stdout is not None
        while True:
            chunk = await process.stdout.read(64 * 1024)
            if not chunk:
                break
            yield chunk

        await process.wait()
        if process.returncode != 0:
            assert process.stderr is not None
            err = await process.stderr.read()
            logger.error("pg_dump failed (exit %d): %s", process.returncode, err.decode())

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.backup.exported",
        resource_type="database",
        details={"filename": filename},
        ip_address=ip,
    )

    return StreamingResponse(
        stream_output(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
