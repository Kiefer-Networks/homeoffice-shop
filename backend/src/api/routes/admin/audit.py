from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import export_audit_csv, get_audit_filter_options, log_admin_action, query_audit_logs
from src.models.dto.audit import AuditFiltersResponse, AuditLogListResponse
from src.models.orm.user import User

router = APIRouter(prefix="/audit", tags=["admin-audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    user_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    items, total = await query_audit_logs(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
        page=page,
        per_page=per_page,
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/filters", response_model=AuditFiltersResponse)
async def get_audit_filters(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await get_audit_filter_options(db)


@router.get("/export")
async def export_audit_logs(
    request: Request,
    user_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    csv_content = await export_audit_csv(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )

    await log_admin_action(
        db, request, admin.id, "admin.audit.exported",
        resource_type="audit_log",
        details={"filters": {"user_id": str(user_id) if user_id else None, "action": action, "resource_type": resource_type}},
    )

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit_log.csv"'},
    )
