from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.models.dto.budget import (
    BudgetAdjustmentCreate,
    BudgetAdjustmentListResponse,
    BudgetAdjustmentResponse,
    BudgetAdjustmentUpdate,
)
from src.models.orm.user import User
from src.services import budget_service

router = APIRouter(prefix="/budgets", tags=["admin-budgets"])


@router.get("/adjustments", response_model=BudgetAdjustmentListResponse)
async def list_adjustments(
    user_id: UUID | None = None,
    q: str | None = None,
    sort: Literal["newest", "oldest", "amount_asc", "amount_desc"] = "newest",
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    items, total = await budget_service.list_adjustments(
        db, user_id=user_id, q=q, sort=sort, page=page, per_page=per_page,
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/adjustments", response_model=BudgetAdjustmentResponse, status_code=201)
async def create_adjustment(
    body: BudgetAdjustmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    adjustment = await budget_service.create_adjustment(
        db,
        user_id=body.user_id,
        amount_cents=body.amount_cents,
        reason=body.reason,
        created_by=admin.id,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.budget.adjustment_created",
        resource_type="budget_adjustment", resource_id=adjustment.id,
        details={
            "target_user_id": str(body.user_id),
            "amount_cents": body.amount_cents,
            "reason": body.reason,
        },
        ip_address=ip, user_agent=ua,
    )
    return adjustment


@router.put("/adjustments/{adjustment_id}", response_model=BudgetAdjustmentResponse)
async def update_adjustment(
    adjustment_id: UUID,
    body: BudgetAdjustmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    adjustment, old_data, enriched = await budget_service.update_adjustment(
        db, adjustment_id, amount_cents=body.amount_cents, reason=body.reason,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.budget.adjustment_updated",
        resource_type="budget_adjustment", resource_id=adjustment.id,
        details={
            "target_user_id": str(adjustment.user_id),
            "old_amount_cents": old_data["amount_cents"],
            "new_amount_cents": body.amount_cents,
            "old_reason": old_data["reason"],
            "new_reason": body.reason,
        },
        ip_address=ip, user_agent=ua,
    )
    return enriched


@router.delete("/adjustments/{adjustment_id}", status_code=204)
async def delete_adjustment(
    adjustment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    _, details = await budget_service.delete_adjustment(db, adjustment_id)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.budget.adjustment_deleted",
        resource_type="budget_adjustment", resource_id=adjustment_id,
        details=details,
        ip_address=ip, user_agent=ua,
    )
    return Response(status_code=204)
