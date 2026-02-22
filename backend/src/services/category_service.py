import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.models.orm.category import Category

_cache: list | None = None
_cache_time: float = 0
_CACHE_TTL = 300  # 5 minutes


def invalidate_cache() -> None:
    global _cache, _cache_time
    _cache = None
    _cache_time = 0


async def list_all(db: AsyncSession) -> list[Category]:
    global _cache, _cache_time
    now = time.monotonic()
    if _cache is not None and (now - _cache_time) < _CACHE_TTL:
        return _cache
    result = await db.execute(
        select(Category).order_by(Category.sort_order, Category.name)
    )
    items = list(result.scalars().all())
    _cache = items
    _cache_time = now
    return items


async def create(
    db: AsyncSession,
    *,
    name: str,
    slug: str,
    description: str | None = None,
    icon: str | None = None,
    sort_order: int = 0,
) -> Category:
    category = Category(
        name=name, slug=slug, description=description, icon=icon, sort_order=sort_order,
    )
    db.add(category)
    await db.flush()
    invalidate_cache()
    return category


_MUTABLE_CATEGORY_FIELDS = {"name", "slug", "description", "icon", "sort_order"}


async def update(
    db: AsyncSession,
    category_id: UUID,
    data: dict,
) -> tuple[Category, dict]:
    category = await db.get(Category, category_id)
    if not category:
        raise NotFoundError("Category not found")

    changes = {}
    for field, value in data.items():
        if field not in _MUTABLE_CATEGORY_FIELDS:
            continue
        if getattr(category, field) != value:
            changes[field] = value
            setattr(category, field, value)
    await db.flush()
    if changes:
        invalidate_cache()
    return category, changes


async def delete(db: AsyncSession, category_id: UUID) -> str:
    category = await db.get(Category, category_id)
    if not category:
        raise NotFoundError("Category not found")
    name = category.name
    await db.delete(category)
    invalidate_cache()
    return name


async def reorder(
    db: AsyncSession,
    items: list[tuple[UUID, int]],
) -> int:
    ids = [item_id for item_id, _ in items]
    result = await db.execute(select(Category).where(Category.id.in_(ids)))
    categories_map = {c.id: c for c in result.scalars().all()}

    for item_id, sort_order in items:
        category = categories_map.get(item_id)
        if not category:
            raise NotFoundError(f"Category {item_id} not found")
        category.sort_order = sort_order
    await db.flush()
    invalidate_cache()
    return len(items)
