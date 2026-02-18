from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import NotFoundError
from src.models.dto import DetailResponse
from src.models.dto.budget import (
    BudgetAdjustmentCreate,
    BudgetAdjustmentResponse,
    BudgetAdjustmentUpdate,
)
from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.user import User
from src.services.budget_service import refresh_budget_cache

router = APIRouter(prefix="/budgets", tags=["admin-budgets"])


@router.get("/adjustments")
async def list_adjustments(
    user_id: UUID | None = None,
    q: str | None = None,
    sort: str = "newest",
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    from sqlalchemy import func, and_
    from sqlalchemy.orm import aliased

    UserTarget = aliased(User, name="user_target")
    UserCreator = aliased(User, name="user_creator")

    conditions = []
    if user_id:
        conditions.append(BudgetAdjustment.user_id == user_id)
    if q:
        search = f"%{q}%"
        conditions.append(
            or_(
                UserTarget.display_name.ilike(search),
                BudgetAdjustment.reason.ilike(search),
            )
        )
    where = and_(*conditions) if conditions else True

    # Build the base query with joins (needed for search filter)
    base_query = (
        select(BudgetAdjustment, UserTarget.display_name, UserCreator.display_name)
        .join(UserTarget, BudgetAdjustment.user_id == UserTarget.id, isouter=True)
        .join(UserCreator, BudgetAdjustment.created_by == UserCreator.id, isouter=True)
        .where(where)
    )

    count_result = await db.execute(
        select(func.count())
        .select_from(BudgetAdjustment)
        .join(UserTarget, BudgetAdjustment.user_id == UserTarget.id, isouter=True)
        .where(where)
    )
    total = count_result.scalar() or 0

    # Sorting
    order_clause = {
        "newest": BudgetAdjustment.created_at.desc(),
        "oldest": BudgetAdjustment.created_at.asc(),
        "amount_asc": BudgetAdjustment.amount_cents.asc(),
        "amount_desc": BudgetAdjustment.amount_cents.desc(),
    }.get(sort, BudgetAdjustment.created_at.desc())

    result = await db.execute(
        base_query.order_by(order_clause)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = result.all()
    items = []
    for adj, user_name, creator_name in rows:
        items.append({
            "id": adj.id,
            "user_id": adj.user_id,
            "amount_cents": adj.amount_cents,
            "reason": adj.reason,
            "created_by": adj.created_by,
            "created_at": adj.created_at,
            "user_display_name": user_name,
            "creator_display_name": creator_name,
        })
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/adjustments", response_model=BudgetAdjustmentResponse, status_code=201)
async def create_adjustment(
    body: BudgetAdjustmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    target = await db.get(User, body.user_id)
    if not target:
        raise NotFoundError("User not found")

    adjustment = BudgetAdjustment(
        user_id=body.user_id,
        amount_cents=body.amount_cents,
        reason=body.reason,
        created_by=admin.id,
    )
    db.add(adjustment)
    await db.flush()
    await refresh_budget_cache(db, body.user_id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.budget.adjustment_created",
        resource_type="budget_adjustment", resource_id=adjustment.id,
        details={
            "target_user_id": str(body.user_id),
            "amount_cents": body.amount_cents,
            "reason": body.reason,
        },
        ip_address=ip,
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
    from sqlalchemy.orm import aliased

    adjustment = await db.get(BudgetAdjustment, adjustment_id)
    if not adjustment:
        raise NotFoundError("Adjustment not found")

    old_amount = adjustment.amount_cents
    old_reason = adjustment.reason

    adjustment.amount_cents = body.amount_cents
    adjustment.reason = body.reason
    await db.flush()

    await refresh_budget_cache(db, adjustment.user_id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.budget.adjustment_updated",
        resource_type="budget_adjustment", resource_id=adjustment.id,
        details={
            "target_user_id": str(adjustment.user_id),
            "old_amount_cents": old_amount,
            "new_amount_cents": body.amount_cents,
            "old_reason": old_reason,
            "new_reason": body.reason,
        },
        ip_address=ip,
    )

    # Re-query with user joins to return display names
    UserTarget = aliased(User, name="user_target")
    UserCreator = aliased(User, name="user_creator")
    result = await db.execute(
        select(BudgetAdjustment, UserTarget.display_name, UserCreator.display_name)
        .join(UserTarget, BudgetAdjustment.user_id == UserTarget.id, isouter=True)
        .join(UserCreator, BudgetAdjustment.created_by == UserCreator.id, isouter=True)
        .where(BudgetAdjustment.id == adjustment_id)
    )
    row = result.one()
    adj, user_name, creator_name = row
    return {
        "id": adj.id,
        "user_id": adj.user_id,
        "amount_cents": adj.amount_cents,
        "reason": adj.reason,
        "created_by": adj.created_by,
        "created_at": adj.created_at,
        "user_display_name": user_name,
        "creator_display_name": creator_name,
    }


@router.delete("/adjustments/{adjustment_id}")
async def delete_adjustment(
    adjustment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    adjustment = await db.get(BudgetAdjustment, adjustment_id)
    if not adjustment:
        raise NotFoundError("Adjustment not found")

    user_id = adjustment.user_id
    details = {
        "target_user_id": str(user_id),
        "amount_cents": adjustment.amount_cents,
        "reason": adjustment.reason,
    }

    await db.delete(adjustment)
    await db.flush()

    await refresh_budget_cache(db, user_id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.budget.adjustment_deleted",
        resource_type="budget_adjustment", resource_id=adjustment_id,
        details=details,
        ip_address=ip,
    )

    return DetailResponse(detail="Adjustment deleted")
