import asyncio
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, and_, or_, literal_column
from sqlalchemy.exc import DataError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import BadRequestError, NotFoundError
from src.core.search import ilike_escape
from src.integrations.amazon.client import AmazonClient
from src.models.dto.product import ProductFieldDiff, RefreshPreviewResponse
from src.models.orm.brand import Brand
from src.models.orm.product import Product
from src.models.orm.category import Category
from src.services.image_service import download_and_store_product_images

logger = logging.getLogger(__name__)

REFRESHABLE_FIELDS = {
    "name": "Name",
    "description": "Description",
    "brand": "Brand",
    "price_cents": "Price",
    "color": "Color",
    "material": "Material",
    "product_dimensions": "Dimensions",
    "item_weight": "Weight",
    "item_model_number": "Model Number",
    "specifications": "Specifications",
    "product_information": "Product Information",
    "variants": "Variants",
}

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
                        Category.name.ilike(ilike_escape(q)),
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
    db: AsyncSession, amazon_client: AmazonClient | None = None,
) -> dict:
    """Refresh prices for all products with amazon_asin."""
    if amazon_client is None:
        amazon_client = AmazonClient()

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


# ── Product CRUD ─────────────────────────────────────────────────────────────

async def get_by_id(db: AsyncSession, product_id: UUID) -> Product:
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    return product


async def resolve_brand_id(db: AsyncSession, brand_name: str) -> UUID:
    result = await db.execute(select(Brand).where(Brand.name == brand_name))
    existing = result.scalar_one_or_none()
    if existing:
        return existing.id
    slug = brand_name.lower().replace(" ", "-").replace(".", "")
    new_brand = Brand(name=brand_name, slug=slug)
    db.add(new_brand)
    await db.flush()
    return new_brand.id


async def create_product(
    db: AsyncSession,
    *,
    category_id: UUID,
    name: str,
    description: str | None = None,
    brand: str | None = None,
    brand_id: UUID | None = None,
    model: str | None = None,
    price_cents: int,
    amazon_asin: str | None = None,
    external_url: str,
    is_active: bool = True,
    max_quantity_per_user: int = 1,
) -> Product:
    if price_cents == 0:
        is_active = False

    if brand and not brand_id:
        brand_id = await resolve_brand_id(db, brand)

    product = Product(
        category_id=category_id,
        name=name,
        description=description,
        brand=brand,
        brand_id=brand_id,
        model=model,
        price_cents=price_cents,
        amazon_asin=amazon_asin,
        external_url=external_url,
        is_active=is_active,
        max_quantity_per_user=max_quantity_per_user,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


_MUTABLE_PRODUCT_FIELDS = {
    "name", "description", "price_cents", "amazon_asin", "brand_id", "category_id",
    "brand", "model", "external_url", "is_active", "max_quantity_per_user",
    "color", "material", "product_dimensions", "item_weight", "item_model_number",
    "specifications", "product_information", "variants",
}


async def update_product(
    db: AsyncSession, product_id: UUID, data: dict,
) -> tuple[Product, dict]:
    product = await get_by_id(db, product_id)

    changes = {}
    for field, value in data.items():
        if field not in _MUTABLE_PRODUCT_FIELDS:
            continue
        old_value = getattr(product, field)
        if old_value != value:
            changes[field] = {"old": old_value, "new": value}
            setattr(product, field, value)

    if product.price_cents == 0 and product.is_active:
        product.is_active = False
        changes["is_active"] = {"old": True, "new": False}

    await db.flush()
    await db.refresh(product)
    return product, changes


async def set_active(db: AsyncSession, product_id: UUID, active: bool) -> Product:
    product = await get_by_id(db, product_id)
    if active and product.price_cents == 0:
        raise BadRequestError("Cannot activate product with price 0")
    product.is_active = active
    await db.flush()
    await db.refresh(product)
    return product


async def archive(db: AsyncSession, product_id: UUID) -> Product:
    product = await get_by_id(db, product_id)
    product.archived_at = datetime.now(timezone.utc)
    product.is_active = False
    await db.flush()
    await db.refresh(product)
    return product


async def restore(db: AsyncSession, product_id: UUID) -> Product:
    product = await get_by_id(db, product_id)
    if not product.archived_at:
        raise BadRequestError("Product is not archived")
    product.archived_at = None
    product.is_active = True
    await db.flush()
    await db.refresh(product)
    return product


# ── Amazon enrichment ────────────────────────────────────────────────────────


async def enrich_from_amazon(
    db: AsyncSession, product: Product, amazon_asin: str
) -> None:
    """Fetch Amazon data for a product and update images, specs, and variants."""
    try:
        client = AmazonClient()
        amazon_data = await client.get_product(amazon_asin)
        if amazon_data:
            main_image = amazon_data.images[0] if amazon_data.images else None
            gallery = amazon_data.images[1:] if len(amazon_data.images) > 1 else []

            paths = await download_and_store_product_images(
                product.id, main_image, gallery, settings.upload_dir, product.name,
            )
            product.image_url = paths.main_image
            product.image_gallery = paths.gallery

            if amazon_data.specifications:
                product.specifications = amazon_data.specifications
            if amazon_data.brand:
                product.brand = amazon_data.brand

            product.color = amazon_data.color
            product.material = amazon_data.material
            product.product_dimensions = amazon_data.product_dimensions
            product.item_weight = amazon_data.item_weight
            product.item_model_number = amazon_data.item_model_number
            product.product_information = amazon_data.product_information

            if amazon_data.variants:
                missing = [v.asin for v in amazon_data.variants if v.price_cents == 0]
                if missing:
                    try:
                        prices = await client.get_variant_prices(missing)
                        for v in amazon_data.variants:
                            if v.asin in prices:
                                v.price_cents = prices[v.asin]
                    except Exception:
                        logger.exception("Failed to fetch variant prices for product %s", product.id)

                product.variants = [v.model_dump() for v in amazon_data.variants]
                variant_prices = [v.price_cents for v in amazon_data.variants if v.price_cents > 0]
                if variant_prices:
                    product.price_min_cents = min(variant_prices)
                    product.price_max_cents = max(variant_prices)

            await db.flush()
            await db.refresh(product)
    except Exception:
        logger.exception("Failed to auto-download images for product %s", product.id)


async def generate_refresh_preview(
    db: AsyncSession, product_id: UUID
) -> RefreshPreviewResponse:
    """Fetch fresh Amazon data and return a diff preview for the product."""
    product = await get_by_id(db, product_id)
    if not product.amazon_asin:
        raise BadRequestError("Product has no Amazon ASIN")

    try:
        client = AmazonClient()
        amazon_data = await client.get_product(product.amazon_asin)
    except Exception:
        logger.exception("ScraperAPI call failed for ASIN %s", product.amazon_asin)
        raise BadRequestError("Amazon API request failed. Please try again later.")

    if not amazon_data:
        raise BadRequestError("Amazon lookup returned no data")

    images_updated = False
    main_image = amazon_data.images[0] if amazon_data.images else None
    gallery = amazon_data.images[1:] if len(amazon_data.images) > 1 else []

    try:
        paths = await download_and_store_product_images(
            product.id, main_image, gallery, settings.upload_dir, product.name,
        )
        product.image_url = paths.main_image
        product.image_gallery = paths.gallery
        images_updated = True
        await db.flush()
    except Exception:
        logger.exception("Image download failed for product %s", product.id)

    if amazon_data.variants:
        variant_asins = [v.asin for v in amazon_data.variants if v.price_cents == 0]
        if variant_asins:
            try:
                prices = await client.get_variant_prices(variant_asins)
                for v in amazon_data.variants:
                    if v.asin in prices:
                        v.price_cents = prices[v.asin]
            except Exception:
                logger.exception("Failed to fetch variant prices")

    diffs: list[ProductFieldDiff] = []
    for field, label in REFRESHABLE_FIELDS.items():
        if field == "variants":
            new_variants = [v.model_dump() for v in amazon_data.variants] if amazon_data.variants else None
            old_variants = product.variants
            if new_variants and new_variants != old_variants:
                diffs.append(ProductFieldDiff(
                    field=field, label=label,
                    old_value=old_variants, new_value=new_variants,
                ))
            continue
        old_value = getattr(product, field)
        new_value = getattr(amazon_data, field, None)
        if new_value is not None and old_value != new_value:
            diffs.append(ProductFieldDiff(
                field=field, label=label,
                old_value=old_value, new_value=new_value,
            ))

    return RefreshPreviewResponse(
        product_id=product.id,
        images_updated=images_updated,
        image_url=product.image_url,
        image_gallery=product.image_gallery,
        diffs=diffs,
    )


async def apply_refresh(
    db: AsyncSession, product_id: UUID, fields: list[str], values: dict
) -> tuple[Product, dict]:
    """Apply selected refresh fields to a product."""
    product = await get_by_id(db, product_id)

    unknown = [f for f in fields if f not in REFRESHABLE_FIELDS]
    if unknown:
        raise BadRequestError(f"Unknown fields: {', '.join(unknown)}")

    changes: dict[str, dict] = {}
    for field in fields:
        if field not in values:
            continue
        old_value = getattr(product, field)
        new_value = values[field]
        setattr(product, field, new_value)
        changes[field] = {"old": old_value, "new": new_value}

    if "variants" in changes and product.variants:
        variant_prices = [v.get("price_cents", 0) for v in product.variants if v.get("price_cents", 0) > 0]
        if variant_prices:
            product.price_min_cents = min(variant_prices)
            product.price_max_cents = max(variant_prices)

    if "brand" in changes and product.brand:
        product.brand_id = await resolve_brand_id(db, product.brand)

    await db.flush()
    await db.refresh(product)
    return product, changes
