import re
import time
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BadRequestError, ConflictError, NotFoundError
from src.models.orm.brand import Brand
from src.models.orm.product import Product

_cache: list | None = None
_cache_time: float = 0
_CACHE_TTL = 300  # 5 minutes


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def invalidate_cache() -> None:
    global _cache, _cache_time
    _cache = None
    _cache_time = 0


async def list_all(db: AsyncSession) -> list[Brand]:
    global _cache, _cache_time
    now = time.monotonic()
    if _cache is not None and (now - _cache_time) < _CACHE_TTL:
        return _cache
    result = await db.execute(select(Brand).order_by(Brand.name.asc()))
    items = list(result.scalars().all())
    _cache = items
    _cache_time = now
    return items


async def create(db: AsyncSession, *, name: str) -> Brand:
    existing = await db.execute(select(Brand).where(Brand.name == name))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Brand '{name}' already exists")

    slug = slugify(name)
    existing_slug = await db.execute(select(Brand).where(Brand.slug == slug))
    if existing_slug.scalar_one_or_none():
        raise ConflictError(f"A brand with a similar name already exists (slug '{slug}')")

    brand = Brand(name=name, slug=slug)
    db.add(brand)
    await db.flush()
    await db.refresh(brand)
    invalidate_cache()
    return brand


async def update(
    db: AsyncSession,
    brand_id: UUID,
    *,
    name: str | None = None,
    logo_url: str | None = None,
) -> tuple[Brand, dict]:
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise NotFoundError("Brand not found")

    changes: dict = {}
    if name is not None and name != brand.name:
        existing = await db.execute(
            select(Brand).where(Brand.name == name, Brand.id != brand_id)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Brand '{name}' already exists")
        new_slug = slugify(name)
        existing_slug = await db.execute(
            select(Brand).where(Brand.slug == new_slug, Brand.id != brand_id)
        )
        if existing_slug.scalar_one_or_none():
            raise ConflictError(f"A brand with a similar name already exists (slug '{new_slug}')")
        changes["name"] = {"old": brand.name, "new": name}
        brand.name = name
        brand.slug = new_slug

    if logo_url is not None:
        changes["logo_url"] = {"old": brand.logo_url, "new": logo_url}
        brand.logo_url = logo_url

    await db.flush()
    await db.refresh(brand)
    invalidate_cache()
    return brand, changes


async def delete(db: AsyncSession, brand_id: UUID) -> str:
    brand = await db.get(Brand, brand_id)
    if not brand:
        raise NotFoundError("Brand not found")

    count_result = await db.execute(
        select(func.count()).select_from(Product).where(Product.brand_id == brand_id)
    )
    product_count = count_result.scalar() or 0
    if product_count > 0:
        raise BadRequestError(
            f"Cannot delete brand with {product_count} associated product(s). "
            "Remove or reassign products first."
        )

    name = brand.name
    await db.delete(brand)
    await db.flush()
    invalidate_cache()
    return name
