import time

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.database import get_db
from src.core.config import settings

router = APIRouter(tags=["health"])


async def _check_database(db: AsyncSession) -> dict:
    try:
        start = time.monotonic()
        await db.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000)
        return {"status": "up", "latency_ms": latency_ms}
    except Exception as e:
        return {"status": "down", "error": str(e)}


async def _check_hibob() -> dict:
    if not settings.hibob_api_key:
        return {"status": "not_configured"}
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                "https://api.hibob.com/v1/people/search",
                headers={
                    "Authorization": f"Basic {settings.hibob_api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"showInactive": False},
            )
            resp.raise_for_status()
        latency_ms = round((time.monotonic() - start) * 1000)
        return {"status": "up", "latency_ms": latency_ms}
    except Exception:
        return {"status": "down"}


async def _check_icecat() -> dict:
    if not settings.icecat_api_token:
        return {"status": "not_configured"}
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://live.icecat.biz/api/",
                params={"Language": "en"},
                headers={"api-token": settings.icecat_api_token},
            )
            resp.raise_for_status()
        latency_ms = round((time.monotonic() - start) * 1000)
        return {"status": "up", "latency_ms": latency_ms}
    except Exception:
        return {"status": "down"}


async def _check_smtp() -> dict:
    if not settings.smtp_host:
        return {"status": "not_configured"}
    return {"status": "configured"}


async def _check_slack() -> dict:
    if not settings.slack_webhook_url:
        return {"status": "not_configured"}
    return {"status": "configured"}


async def _check_disk() -> dict:
    import shutil
    from pathlib import Path

    uploads_path = Path("/app/uploads")
    if not uploads_path.exists():
        uploads_path = Path("uploads")
        uploads_path.mkdir(exist_ok=True)

    try:
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
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks = {
        "database": await _check_database(db),
        "smtp": await _check_smtp(),
        "slack": await _check_slack(),
        "disk": await _check_disk(),
    }

    overall = "healthy" if checks["database"]["status"] == "up" else "unhealthy"

    return {
        "status": overall,
        "version": "1.0.0",
        "checks": checks,
    }
