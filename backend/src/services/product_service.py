import asyncio
import logging
import re
from uuid import UUID

from sqlalchemy import select, func, and_, or_, literal_column
from sqlalchemy.exc import DataError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.product import Product
from src.models.orm.category import Category

logger = logging.getLogger(__name__)

# Bidirectional synonym map for search expansion
SEARCH_SYNONYMS: dict[str, list[str]] = {
    "notebook": ["laptop"],
    "laptop": ["notebook"],
    "headphones": ["earbuds", "earphones"],
    "earbuds": ["headphones", "earphones"],
    "earphones": ["headphones", "earbuds"],
    "monitor": ["display", "screen"],
    "display": ["monitor", "screen"],
    "screen": ["monitor", "display"],
    "keyboard": ["keeb"],
    "keeb": ["keyboard"],
    "mouse": ["mice"],
    "mice": ["mouse"],
    "phone": ["smartphone", "mobile"],
    "smartphone": ["phone", "mobile"],
    "mobile": ["phone", "smartphone"],
    "cable": ["cord", "wire"],
    "cord": ["cable", "wire"],
    "wire": ["cable", "cord"],
    "charger": ["adapter", "power supply"],
    "adapter": ["charger", "power supply"],
    "speaker": ["speakers"],
    "speakers": ["speaker"],
    "mic": ["microphone"],
    "microphone": ["mic"],
    "webcam": ["camera"],
    "camera": ["webcam"],
    "hdd": ["hard drive"],
    "hard drive": ["hdd"],
    "ssd": ["solid state drive"],
    "solid state drive": ["ssd"],
}


def _build_prefix_tsquery(q: str) -> str | None:
    """Build a tsquery string with prefix matching on the last term.

    E.g. "wire key" -> "wire & key:*"
    """
    words = q.strip().split()
    if not words:
        return None
    # Sanitize: keep only alphanumeric chars per word
    sanitized = [re.sub(r"[^\w]", "", w) for w in words]
    sanitized = [w for w in sanitized if w]
    if not sanitized:
        return None
    if len(sanitized) == 1:
        return f"{sanitized[0]}:*"
    return " & ".join(sanitized[:-1]) + f" & {sanitized[-1]}:*"


def _expand_with_synonyms(q: str) -> str:
    """Expand query terms with known synonyms using OR.

    E.g. "notebook case" -> "notebook | laptop case"
    """
    words = q.lower().strip().split()
    expanded_parts: list[str] = []
    for word in words:
        clean = re.sub(r"[^\w]", "", word)
        if clean in SEARCH_SYNONYMS:
            group = [clean] + SEARCH_SYNONYMS[clean]
            expanded_parts.append("(" + " | ".join(group) + ")")
        else:
            expanded_parts.append(clean)
    return " ".join(expanded_parts)


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
    include_archived: bool = False,
    archived_only: bool = False,
    sort: str = "relevance",
    page: int = 1,
    per_page: int = 20,
) -> dict:
    conditions = []

    if archived_only:
        conditions.append(Product.archived_at.isnot(None))
    elif not include_archived:
        conditions.append(Product.archived_at.is_(None))

    # Don't filter by is_active when viewing archived products
    if is_active is not None and not archived_only:
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
        try:
            search_conditions: list = []

            # Strategy 1: websearch_to_tsquery — supports AND, OR, -exclude, "phrases"
            ws_query = func.websearch_to_tsquery("english", q)
            search_conditions.append(Product.search_vector.op("@@")(ws_query))

            # Strategy 2: Prefix query for partial typing / autocomplete
            prefix_expr = _build_prefix_tsquery(q)
            if prefix_expr:
                prefix_query = func.to_tsquery("english", prefix_expr)
                search_conditions.append(
                    Product.search_vector.op("@@")(prefix_query)
                )

            # Strategy 3: Synonym expansion
            expanded = _expand_with_synonyms(q)
            if expanded.lower() != q.lower().strip():
                syn_query = func.plainto_tsquery("english", expanded)
                search_conditions.append(
                    Product.search_vector.op("@@")(syn_query)
                )

            # Strategy 4: Category name subquery (ILIKE + similarity)
            search_conditions.append(Product.category_id.in_(
                select(Category.id).where(
                    or_(
                        Category.name.ilike(f"%{q.replace(chr(92), chr(92)*2).replace('%', chr(92)+'%').replace('_', chr(92)+'_')}%"),
                        func.similarity(Category.name, q) > 0.3,
                    )
                )
            ))

            # Strategy 5: Trigram similarity (threshold 0.3)
            search_conditions.append(func.similarity(Product.name, q) > 0.3)
            search_conditions.append(func.similarity(Product.brand, q) > 0.3)

            conditions.append(or_(*search_conditions))
        except DataError:
            logger.warning("Malformed search query %r, falling back to similarity", q)
            conditions.append(
                or_(
                    func.similarity(Product.name, q) > 0.3,
                    func.similarity(Product.brand, q) > 0.3,
                )
            )

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
        # Blended score: ts_rank * 2 + max(name_sim, brand_sim) + prefix_rank
        ws_query = func.websearch_to_tsquery("english", q)
        ts_rank = func.ts_rank(Product.search_vector, ws_query)
        name_sim = func.coalesce(func.similarity(Product.name, q), 0)
        brand_sim = func.coalesce(func.similarity(Product.brand, q), 0)
        best_sim = func.greatest(name_sim, brand_sim)

        prefix_rank = literal_column("0")
        prefix_expr = _build_prefix_tsquery(q)
        if prefix_expr:
            prefix_tsq = func.to_tsquery("english", prefix_expr)
            prefix_rank = func.ts_rank(Product.search_vector, prefix_tsq)

        blended = ts_rank * 2 + best_sim + prefix_rank
        query = query.order_by(blended.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    products = list(result.scalars().all())

    # Build facets concurrently
    active_condition = Product.is_active.is_(True)

    async def _brand_facets():
        r = await db.execute(
            select(Product.brand, func.count())
            .where(active_condition)
            .where(Product.brand.isnot(None))
            .group_by(Product.brand)
            .order_by(Product.brand)
        )
        return [{"value": b, "count": c} for b, c in r.all()]

    async def _cat_facets():
        r = await db.execute(
            select(Category.id, Category.slug, Category.name, func.count(Product.id))
            .join(Product, Product.category_id == Category.id)
            .where(active_condition)
            .group_by(Category.id, Category.slug, Category.name)
            .order_by(func.count(Product.id).desc())
        )
        return [
            {"id": str(cid), "slug": slug, "name": name, "count": cnt}
            for cid, slug, name, cnt in r.all()
        ]

    async def _color_facets():
        r = await db.execute(
            select(Product.color, func.count())
            .where(active_condition)
            .where(Product.color.isnot(None))
            .group_by(Product.color)
            .order_by(func.count().desc())
            .limit(20)
        )
        return [{"value": c, "count": cnt} for c, cnt in r.all()]

    async def _material_facets():
        r = await db.execute(
            select(Product.material, func.count())
            .where(active_condition)
            .where(Product.material.isnot(None))
            .group_by(Product.material)
            .order_by(func.count().desc())
            .limit(20)
        )
        return [{"value": m, "count": cnt} for m, cnt in r.all()]

    async def _price_range():
        r = await db.execute(
            select(func.min(Product.price_cents), func.max(Product.price_cents)).where(
                active_condition
            )
        )
        row = r.one_or_none()
        return {"min_cents": row[0] or 0, "max_cents": row[1] or 0} if row else {"min_cents": 0, "max_cents": 0}

    # Execute sequentially — all coroutines share the same db session
    brands = await _brand_facets()
    categories = await _cat_facets()
    colors = await _color_facets()
    materials = await _material_facets()
    price_range = await _price_range()

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
    sem = asyncio.Semaphore(5)

    async def _refresh_one(product: Product) -> bool:
        async with sem:
            try:
                new_price = await amazon_client.get_current_price(product.amazon_asin)
                if new_price and new_price != product.price_cents:
                    product.price_cents = new_price
                    return True
            except Exception:
                logger.exception("Failed to refresh price for product %s", product.id)
                raise
            return False

    results = await asyncio.gather(
        *[_refresh_one(p) for p in products], return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            errors += 1
        elif r:
            updated += 1

    await db.flush()
    return {"total": len(products), "updated": updated, "errors": errors}
