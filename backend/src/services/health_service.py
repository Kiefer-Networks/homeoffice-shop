import asyncio
import logging
import os
import shutil
import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

logger = logging.getLogger(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "dev")


async def check_database(db: AsyncSession) -> dict:
    """Check database connectivity and measure latency."""
    try:
        start = time.monotonic()
        await db.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000)
        return {"status": "up", "latency_ms": latency_ms}
    except Exception:
        return {"status": "down"}


async def check_smtp() -> dict:
    """Check whether SMTP is configured."""
    from src.services.settings_service import get_setting

    if not get_setting("smtp_host"):
        return {"status": "not_configured"}
    return {"status": "configured"}


async def check_disk() -> dict:
    """Check disk usage for the uploads directory."""
    uploads_path = Path("/app/uploads")
    if not uploads_path.exists():
        uploads_path = Path("uploads")
        uploads_path.mkdir(exist_ok=True)

    def _sync_disk_check():
        usage = shutil.disk_usage(uploads_path)
        uploads_mb = 0
        if uploads_path.exists():
            uploads_mb = sum(
                f.stat().st_size for f in uploads_path.rglob("*") if f.is_file()
            ) // (1024 * 1024)
        return {
            "status": "ok",
            "uploads_mb": uploads_mb,
            "free_mb": usage.free // (1024 * 1024),
        }

    try:
        return await asyncio.to_thread(_sync_disk_check)
    except Exception:
        return {"status": "error"}


async def get_basic_health(db: AsyncSession) -> tuple[dict, int]:
    """Run basic health check (DB only). Returns (response_body, status_code)."""
    db_status = await check_database(db)
    overall = "healthy" if db_status["status"] == "up" else "unhealthy"
    status_code = 200 if overall == "healthy" else 503
    return {"status": overall}, status_code


async def get_detailed_health(db: AsyncSession) -> dict:
    """Run all health checks and return detailed status."""
    checks = {
        "database": await check_database(db),
        "smtp": await check_smtp(),
        "disk": await check_disk(),
    }

    overall = "healthy" if checks["database"]["status"] == "up" else "unhealthy"

    return {
        "status": overall,
        "version": APP_VERSION,
        "checks": checks,
    }
