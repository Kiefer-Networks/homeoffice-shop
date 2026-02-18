import re
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import BadRequestError, ConflictError, NotFoundError
from src.models.dto.brand import BrandCreate, BrandResponse, BrandUpdate
from src.models.orm.brand import Brand
from src.models.orm.product import Product
from src.models.orm.user import User

router = APIRouter(prefix="/brands", tags=["admin-brands"])


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


@router.get("", response_model=list[BrandResponse])
async def list_brands(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(Brand).order_by(Brand.name.asc())
    )
    return list(result.scalars().all())


@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(
    body: BrandCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # Check uniqueness
    existing = await db.execute(
        select(Brand).where(Brand.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Brand '{body.name}' already exists")

    slug = _slugify(body.name)
    brand = Brand(name=body.name, slug=slug)
    db.add(brand)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.brand.created",
        resource_type="brand", resource_id=brand.id,
        details={"name": brand.name}, ip_address=ip,
    )

    await db.refresh(brand)
    return brand


@router.put("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: UUID,
    body: BrandUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise NotFoundError("Brand not found")

    changes = {}
    if body.name is not None and body.name != brand.name:
        # Check uniqueness
        existing = await db.execute(
            select(Brand).where(Brand.name == body.name, Brand.id != brand_id)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Brand '{body.name}' already exists")
        changes["name"] = {"old": brand.name, "new": body.name}
        brand.name = body.name
        brand.slug = _slugify(body.name)

    if body.logo_url is not None:
        changes["logo_url"] = {"old": brand.logo_url, "new": body.logo_url}
        brand.logo_url = body.logo_url

    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.brand.updated",
        resource_type="brand", resource_id=brand.id,
        details=changes, ip_address=ip,
    )

    await db.refresh(brand)
    return brand


@router.delete("/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise NotFoundError("Brand not found")

    # Check for products using this brand
    count_result = await db.execute(
        select(func.count()).select_from(Product).where(Product.brand_id == brand_id)
    )
    product_count = count_result.scalar() or 0
    if product_count > 0:
        raise BadRequestError(
            f"Cannot delete brand with {product_count} associated product(s). "
            "Remove or reassign products first."
        )

    brand_name = brand.name
    await db.delete(brand)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.brand.deleted",
        resource_type="brand", resource_id=brand_id,
        details={"name": brand_name}, ip_address=ip,
    )
