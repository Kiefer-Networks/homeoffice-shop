from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import NotFoundError
from src.models.dto.budget import BudgetAdjustmentCreate, BudgetAdjustmentResponse
from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.user import User
from src.services.budget_service import refresh_budget_cache

router = APIRouter(prefix="/budgets", tags=["admin-budgets"])


@router.get("/adjustments")
async def list_adjustments(
    user_id: UUID | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from sqlalchemy import func, and_
    from sqlalchemy.orm import aliased

    UserTarget = aliased(User, name="user_target")
    UserCreator = aliased(User, name="user_creator")

    conditions = []
    if user_id:
        conditions.append(BudgetAdjustment.user_id == user_id)
    where = and_(*conditions) if conditions else True

    count_result = await db.execute(
        select(func.count()).select_from(BudgetAdjustment).where(where)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(BudgetAdjustment, UserTarget.display_name, UserCreator.display_name)
        .join(UserTarget, BudgetAdjustment.user_id == UserTarget.id, isouter=True)
        .join(UserCreator, BudgetAdjustment.created_by == UserCreator.id, isouter=True)
        .where(where)
        .order_by(BudgetAdjustment.created_at.desc())
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
    admin: User = Depends(require_admin),
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
