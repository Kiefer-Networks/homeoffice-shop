from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.models.dto import DetailResponse
from src.models.dto.category import CategoryCreate, CategoryReorderItem, CategoryResponse, CategoryUpdate
from src.models.orm.user import User
from src.services import category_service

router = APIRouter(prefix="/categories", tags=["admin-categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    return await category_service.list_all(db)


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    category = await category_service.create(
        db, name=body.name, slug=body.slug,
        description=body.description, icon=body.icon, sort_order=body.sort_order,
    )

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.category.created",
        resource_type="category", resource_id=category.id,
        details={"name": category.name}, ip_address=ip,
    )
    return category


@router.put("/reorder", response_model=DetailResponse)
async def reorder_categories(
    items: list[CategoryReorderItem],
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    count = await category_service.reorder(
        db, [(item.id, item.sort_order) for item in items],
    )

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.category.reordered",
        resource_type="category",
        details={"count": count}, ip_address=ip,
    )
    return {"detail": "Categories reordered"}


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    category, changes = await category_service.update(
        db, category_id, body.model_dump(exclude_unset=True),
    )

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.category.updated",
        resource_type="category", resource_id=category.id,
        details=changes, ip_address=ip,
    )
    return category


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    name = await category_service.delete(db, category_id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.category.deleted",
        resource_type="category", resource_id=category_id,
        details={"name": name}, ip_address=ip,
    )

    return Response(status_code=204)
