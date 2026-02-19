import asyncio

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import audit_context
from src.models.dto.hibob import (
    HiBobPurchaseSyncLogListResponse,
    HiBobSyncLogListResponse,
)
from src.models.orm.user import User
from src.services.hibob_service import (
    guarded_employee_sync,
    guarded_purchase_sync,
    is_employee_sync_locked,
    is_purchase_sync_locked,
    is_purchase_sync_running,
    get_sync_logs,
    get_purchase_sync_logs,
)

router = APIRouter(prefix="/hibob", tags=["admin-hibob"])


@router.post("/sync", status_code=202)
async def trigger_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if is_employee_sync_locked():
        return JSONResponse(status_code=409, content={"detail": "Sync already in progress"})
    ip, ua = audit_context(request)
    asyncio.create_task(guarded_employee_sync(admin.id, ip, ua))
    return {"detail": "Sync started in background"}


@router.get("/sync-log", response_model=HiBobSyncLogListResponse)
async def get_sync_logs_endpoint(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    items, total = await get_sync_logs(db, page=page, per_page=per_page)
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/purchase-sync-status")
async def purchase_sync_status(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Return whether a purchase sync is currently running."""
    running = await is_purchase_sync_running(db)
    return {"running": running}


@router.post("/purchase-sync", status_code=202)
async def trigger_purchase_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if is_purchase_sync_locked():
        return JSONResponse(status_code=409, content={"detail": "Purchase sync already in progress"})
    ip, ua = audit_context(request)
    asyncio.create_task(guarded_purchase_sync(admin.id, ip, ua))
    return {"detail": "Purchase sync started in background"}


@router.get("/purchase-sync-log", response_model=HiBobPurchaseSyncLogListResponse)
async def get_purchase_sync_logs_endpoint(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    items, total = await get_purchase_sync_logs(db, page=page, per_page=per_page)
    return {"items": items, "total": total, "page": page, "per_page": per_page}
