from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.dto.user import UserProbationOverride, UserRoleUpdate
from src.models.orm.user import User
from src.repositories import user_repo

router = APIRouter(prefix="/users", tags=["admin-users"])


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    q: str | None = Query(None),
    department: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    sort: str = Query("name_asc"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
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


@router.put("/{user_id}/role")
async def update_user_role(
    user_id: UUID,
    body: UserRoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if body.role not in ("employee", "admin"):
        raise BadRequestError("Invalid role. Must be 'employee' or 'admin'.")

    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    old_role = target.role
    target.role = body.role
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.user.role_changed",
        resource_type="user", resource_id=user_id,
        details={"old_role": old_role, "new_role": body.role},
        ip_address=ip,
    )

    return {"detail": f"Role updated to {body.role}"}


@router.put("/{user_id}/probation-override")
async def update_probation_override(
    user_id: UUID,
    body: UserProbationOverride,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
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
