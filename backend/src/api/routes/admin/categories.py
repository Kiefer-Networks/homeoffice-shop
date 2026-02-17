from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import NotFoundError
from src.models.dto import DetailResponse
from src.models.dto.category import CategoryCreate, CategoryResponse, CategoryUpdate
from src.models.orm.category import Category
from src.models.orm.user import User

router = APIRouter(prefix="/categories", tags=["admin-categories"])


@router.get("", response_model=list[CategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Category).order_by(Category.sort_order, Category.name)
    )
    return list(result.scalars().all())


@router.post("", response_model=CategoryResponse, status_code=201)
async def create_category(
    body: CategoryCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    category = Category(
        name=body.name,
        slug=body.slug,
        description=body.description,
        icon=body.icon,
        sort_order=body.sort_order,
    )
    db.add(category)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.category.created",
        resource_type="category", resource_id=category.id,
        details={"name": category.name}, ip_address=ip,
    )
    return category


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    body: CategoryUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    category = await db.get(Category, category_id)
    if not category:
        raise NotFoundError("Category not found")

    changes = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        if getattr(category, field) != value:
            changes[field] = value
            setattr(category, field, value)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.category.updated",
        resource_type="category", resource_id=category.id,
        details=changes, ip_address=ip,
    )
    return category


class ReorderItem(BaseModel):
    id: UUID
    sort_order: int


@router.put("/reorder", response_model=DetailResponse)
async def reorder_categories(
    items: list[ReorderItem],
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ids = [item.id for item in items]
    result = await db.execute(select(Category).where(Category.id.in_(ids)))
    categories_map = {c.id: c for c in result.scalars().all()}

    for item in items:
        category = categories_map.get(item.id)
        if not category:
            raise NotFoundError(f"Category {item.id} not found")
        category.sort_order = item.sort_order
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.category.reordered",
        resource_type="category",
        details={"count": len(items)}, ip_address=ip,
    )
    return {"detail": "Categories reordered"}


@router.delete("/{category_id}", status_code=204)
async def delete_category(
    category_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    category = await db.get(Category, category_id)
    if not category:
        raise NotFoundError("Category not found")

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.category.deleted",
        resource_type="category", resource_id=category.id,
        details={"name": category.name}, ip_address=ip,
    )

    await db.delete(category)
    return Response(status_code=204)
