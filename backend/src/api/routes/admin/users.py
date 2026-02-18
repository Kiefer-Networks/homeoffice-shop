from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin, require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.dto import DetailResponse
from src.models.dto.budget import (
    UserBudgetOverrideCreate,
    UserBudgetOverrideResponse,
    UserBudgetOverrideUpdate,
)
from src.models.dto.user import (
    UserAdminListResponse,
    UserDetailResponse,
    UserProbationOverride,
    UserRoleUpdate,
    UserSearchResult,
)
from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.user import User
from src.models.orm.user_budget_override import UserBudgetOverride
from src.notifications.service import notify_user_email
from src.repositories import user_repo
from src.services import budget_service, order_service
from src.services.auth_service import logout as revoke_user_sessions

router = APIRouter(prefix="/users", tags=["admin-users"])

VALID_SORTS = {"name_asc", "name_desc", "department", "start_date", "budget"}


@router.get("", response_model=UserAdminListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, max_length=200),
    department: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    sort: Literal["name_asc", "name_desc", "department", "start_date", "budget"] = Query("name_asc"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    users, total = await user_repo.get_all(
        db,
        page=page,
        per_page=per_page,
        q=q,
        department=department,
        role=role,
        is_active=is_active,
        sort=sort,
    )
    return {"items": users, "total": total, "page": page, "per_page": per_page}


@router.get("/search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(min_length=1),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    users = await user_repo.search_active(db, q, limit)
    return users


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    # Get orders
    orders, _ = await order_service.get_orders(db, user_id=user_id, page=1, per_page=100)

    # Get adjustments
    result = await db.execute(
        select(BudgetAdjustment)
        .where(BudgetAdjustment.user_id == user_id)
        .order_by(BudgetAdjustment.created_at.desc())
    )
    adjustments = [
        {
            "id": a.id,
            "user_id": a.user_id,
            "amount_cents": a.amount_cents,
            "reason": a.reason,
            "created_by": a.created_by,
            "created_at": a.created_at,
        }
        for a in result.scalars().all()
    ]

    # Budget summary
    spent = await budget_service.get_live_spent_cents(db, user_id)
    adjustment_total = await budget_service.get_live_adjustment_cents(db, user_id)
    available = target.total_budget_cents + adjustment_total - spent

    # Budget timeline and overrides
    rules = await budget_service.get_budget_rules(db)
    overrides = await budget_service.get_user_overrides(db, user_id)
    timeline = []
    if target.start_date:
        timeline = budget_service.get_budget_timeline(target.start_date, rules, overrides)

    override_dicts = [
        {
            "id": o.id,
            "user_id": o.user_id,
            "effective_from": o.effective_from,
            "effective_until": o.effective_until,
            "initial_cents": o.initial_cents,
            "yearly_increment_cents": o.yearly_increment_cents,
            "reason": o.reason,
            "created_by": o.created_by,
            "created_at": o.created_at,
        }
        for o in overrides
    ]

    return {
        "user": target,
        "orders": orders,
        "adjustments": adjustments,
        "budget_summary": {
            "total_budget_cents": target.total_budget_cents,
            "spent_cents": spent,
            "adjustment_cents": adjustment_total,
            "available_cents": available,
        },
        "budget_timeline": timeline,
        "budget_overrides": override_dicts,
    }


@router.put("/{user_id}/role", response_model=DetailResponse)
async def update_user_role(
    user_id: UUID,
    body: UserRoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise BadRequestError("Cannot change your own role")

    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    old_role = target.role
    target.role = body.role
    await db.flush()

    # Invalidate all sessions so the user gets a fresh token with the new role
    await revoke_user_sessions(db, user_id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.user.role_changed",
        resource_type="user", resource_id=user_id,
        details={"old_role": old_role, "new_role": body.role},
        ip_address=ip,
    )

    await notify_user_email(
        target.email,
        subject="Your Role Has Been Updated",
        template_name="role_changed.html",
        context={"old_role": old_role, "new_role": body.role},
    )

    return {"detail": f"Role updated to {body.role}"}


@router.put("/{user_id}/probation-override", response_model=DetailResponse)
async def update_probation_override(
    user_id: UUID,
    body: UserProbationOverride,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    target.probation_override = body.probation_override
    await db.flush()

    action = (
        "admin.user.early_access_granted"
        if body.probation_override
        else "admin.user.early_access_revoked"
    )
    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action=action,
        resource_type="user", resource_id=user_id,
        ip_address=ip,
    )

    return {"detail": f"Probation override set to {body.probation_override}"}


# ── Budget Overrides ──────────────────────────────────────────────────────────

@router.post("/{user_id}/budget-overrides", response_model=UserBudgetOverrideResponse, status_code=201)
async def create_budget_override(
    user_id: UUID,
    body: UserBudgetOverrideCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    override = UserBudgetOverride(
        user_id=user_id,
        effective_from=body.effective_from,
        effective_until=body.effective_until,
        initial_cents=body.initial_cents,
        yearly_increment_cents=body.yearly_increment_cents,
        reason=body.reason,
        created_by=staff.id,
    )
    db.add(override)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_override.created",
        resource_type="user_budget_override", resource_id=override.id,
        details={"user_id": str(user_id), "reason": body.reason},
        ip_address=ip,
    )

    return override


@router.put("/{user_id}/budget-overrides/{override_id}", response_model=UserBudgetOverrideResponse)
async def update_budget_override(
    user_id: UUID,
    override_id: UUID,
    body: UserBudgetOverrideUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    override = await db.get(UserBudgetOverride, override_id)
    if not override or override.user_id != user_id:
        raise NotFoundError("Budget override not found")

    if body.effective_from is not None:
        override.effective_from = body.effective_from
    if body.effective_until is not None:
        override.effective_until = body.effective_until
    if body.initial_cents is not None:
        override.initial_cents = body.initial_cents
    if body.yearly_increment_cents is not None:
        override.yearly_increment_cents = body.yearly_increment_cents
    if body.reason is not None:
        override.reason = body.reason
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_override.updated",
        resource_type="user_budget_override", resource_id=override_id,
        details=body.model_dump(exclude_none=True, mode="json"),
        ip_address=ip,
    )

    return override


@router.delete("/{user_id}/budget-overrides/{override_id}", status_code=204)
async def delete_budget_override(
    user_id: UUID,
    override_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    override = await db.get(UserBudgetOverride, override_id)
    if not override or override.user_id != user_id:
        raise NotFoundError("Budget override not found")

    await db.delete(override)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_override.deleted",
        resource_type="user_budget_override", resource_id=override_id,
        details={"user_id": str(user_id)},
        ip_address=ip,
    )
