import logging
from uuid import UUID

from sqlalchemy import select, func, text, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.product import Product
from src.models.orm.category import Category

logger = logging.getLogger(__name__)


async def search_products(
    db: AsyncSession,
    *,
    q: str | None = None,
    category_id: UUID | None = None,
    brand: str | None = None,
    color: str | None = None,
    material: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    is_active: bool = True,
    sort: str = "relevance",
    page: int = 1,
    per_page: int = 20,
) -> dict:
    conditions = []

    if is_active is not None:
        conditions.append(Product.is_active == is_active)
    if category_id:
        conditions.append(Product.category_id == category_id)
    if brand:
        brands = [b.strip() for b in brand.split(",")]
        conditions.append(Product.brand.in_(brands))
    if color:
        colors = [c.strip() for c in color.split(",")]
        conditions.append(Product.color.in_(colors))
    if material:
        materials = [m.strip() for m in material.split(",")]
        conditions.append(Product.material.in_(materials))
    if price_min is not None:
        conditions.append(Product.price_cents >= price_min * 100)
    if price_max is not None:
        conditions.append(Product.price_cents <= price_max * 100)

    if q:
        ts_query = func.plainto_tsquery("english", q)
        search_condition = or_(
            Product.search_vector.op("@@")(ts_query),
            func.similarity(Product.name, q) > 0.1,
            func.similarity(Product.brand, q) > 0.1,
        )
        conditions.append(search_condition)

    where = and_(*conditions) if conditions else True

    count_result = await db.execute(
        select(func.count()).select_from(Product).where(where)
    )
    total = count_result.scalar() or 0

    query = select(Product).where(where)

    if sort == "price_asc":
        query = query.order_by(Product.price_cents.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price_cents.desc())
    elif sort == "name_asc":
        query = query.order_by(Product.name.asc())
    elif sort == "newest":
        query = query.order_by(Product.created_at.desc())
    elif q and sort == "relevance":
        ts_query = func.plainto_tsquery("english", q)
        query = query.order_by(
            func.ts_rank(Product.search_vector, ts_query).desc()
        )
    else:
        query = query.order_by(Product.created_at.desc())

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    products = list(result.scalars().all())

    # Build facets
    active_condition = Product.is_active == True
    brand_facets = await db.execute(
        select(Product.brand, func.count())
        .where(active_condition)
        .where(Product.brand.isnot(None))
        .group_by(Product.brand)
        .order_by(func.count().desc())
        .limit(20)
    )
    brands = [{"value": b, "count": c} for b, c in brand_facets.all()]

    cat_facets = await db.execute(
        select(Category.id, Category.slug, Category.name, func.count(Product.id))
        .join(Product, Product.category_id == Category.id)
        .where(active_condition)
        .group_by(Category.id, Category.slug, Category.name)
        .order_by(func.count(Product.id).desc())
    )
    categories = [
        {"id": str(cid), "slug": slug, "name": name, "count": cnt}
        for cid, slug, name, cnt in cat_facets.all()
    ]

    color_facets = await db.execute(
        select(Product.color, func.count())
        .where(active_condition)
        .where(Product.color.isnot(None))
        .group_by(Product.color)
        .order_by(func.count().desc())
        .limit(20)
    )
    colors = [{"value": c, "count": cnt} for c, cnt in color_facets.all()]

    material_facets = await db.execute(
        select(Product.material, func.count())
        .where(active_condition)
        .where(Product.material.isnot(None))
        .group_by(Product.material)
        .order_by(func.count().desc())
        .limit(20)
    )
    materials = [{"value": m, "count": cnt} for m, cnt in material_facets.all()]

    price_result = await db.execute(
        select(func.min(Product.price_cents), func.max(Product.price_cents)).where(
            active_condition
        )
    )
    price_row = price_result.one_or_none()
    price_range = {
        "min_cents": price_row[0] or 0,
        "max_cents": price_row[1] or 0,
    } if price_row else {"min_cents": 0, "max_cents": 0}

    return {
        "items": products,
        "total": total,
        "page": page,
        "per_page": per_page,
        "facets": {
            "brands": brands,
            "categories": categories,
            "colors": colors,
            "materials": materials,
            "price_range": price_range,
        },
    }


async def refresh_all_prices(
    db: AsyncSession, amazon_client
) -> dict:
    """Refresh prices for all products with amazon_asin."""
    result = await db.execute(
        select(Product).where(Product.amazon_asin.isnot(None))
    )
    products = list(result.scalars().all())

    updated = 0
    errors = 0

    for product in products:
        try:
            new_price = await amazon_client.get_current_price(product.amazon_asin)
            if new_price and new_price != product.price_cents:
                product.price_cents = new_price
                updated += 1
        except Exception:
            errors += 1
            logger.exception("Failed to refresh price for product %s", product.id)

    await db.flush()
    return {"total": len(products), "updated": updated, "errors": errors}
