from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin, require_staff
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
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
from src.models.orm.user import User
from src.notifications.service import notify_user_email
from src.services import user_service

router = APIRouter(prefix="/users", tags=["admin-users"])


@router.get("/departments", response_model=list[str])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    return await user_service.get_departments(db)


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
    return await user_service.list_users(
        db, page=page, per_page=per_page, q=q,
        department=department, role=role, is_active=is_active, sort=sort,
    )


@router.get("/search", response_model=list[UserSearchResult])
async def search_users(
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(20, le=50),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    return await user_service.search_users(db, q, limit)


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user_detail(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    return await user_service.get_user_detail(db, user_id)


@router.put("/{user_id}/role", response_model=DetailResponse)
async def update_user_role(
    user_id: UUID,
    body: UserRoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target, old_role = await user_service.change_role(db, user_id, body.role, admin.id)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.user.role_changed",
        resource_type="user", resource_id=user_id,
        details={
            "old_role": old_role,
            "new_role": body.role,
            "target_user_email": target.email,
        },
        ip_address=ip, user_agent=ua,
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
    await user_service.set_probation_override(db, user_id, body.probation_override)

    action = (
        "admin.user.early_access_granted"
        if body.probation_override
        else "admin.user.early_access_revoked"
    )
    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action=action,
        resource_type="user", resource_id=user_id,
        details={"probation_override": body.probation_override},
        ip_address=ip, user_agent=ua,
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
    override = await user_service.create_budget_override(
        db, user_id,
        effective_from=body.effective_from,
        effective_until=body.effective_until,
        initial_cents=body.initial_cents,
        yearly_increment_cents=body.yearly_increment_cents,
        reason=body.reason,
        created_by=staff.id,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_override.created",
        resource_type="user_budget_override", resource_id=override.id,
        details={
            "user_id": str(user_id),
            "reason": body.reason,
            "effective_from": str(body.effective_from),
            "effective_until": str(body.effective_until) if body.effective_until else None,
            "initial_cents": body.initial_cents,
            "yearly_increment_cents": body.yearly_increment_cents,
        },
        ip_address=ip, user_agent=ua,
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
    data = body.model_dump(exclude_unset=True)
    override = await user_service.update_budget_override(db, user_id, override_id, data)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_override.updated",
        resource_type="user_budget_override", resource_id=override_id,
        details={
            "user_id": str(user_id),
            **{k: (str(v) if hasattr(v, 'isoformat') else v) for k, v in data.items()},
        },
        ip_address=ip, user_agent=ua,
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
    await user_service.delete_budget_override(db, user_id, override_id)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_override.deleted",
        resource_type="user_budget_override", resource_id=override_id,
        details={"user_id": str(user_id)},
        ip_address=ip, user_agent=ua,
    )

    return Response(status_code=204)
