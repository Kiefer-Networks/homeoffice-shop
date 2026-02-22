import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BadRequestError
from src.models.orm.cart_item import CartItem
from src.models.orm.product import Product
from src.services.budget_service import get_available_budget_cents
from src.services.settings_service import get_setting_int

logger = logging.getLogger(__name__)


async def get_cart(db: AsyncSession, user_id: UUID) -> dict:
    result = await db.execute(
        select(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.added_at)
    )
    rows = result.all()

    items = []
    total_at_add = 0
    total_current = 0
    has_price_changes = False
    has_unavailable = False

    for cart_item, product in rows:
        # If cart item has a variant, use variant price as current price.
        # Use dict lookup (O(1)) instead of linear scan (O(n)) over variants.
        current_price = product.price_cents
        if cart_item.variant_asin and product.variants:
            variant_map = {v.get("asin"): v for v in product.variants}
            matched = variant_map.get(cart_item.variant_asin)
            if matched and matched.get("price_cents", 0) > 0:
                current_price = matched["price_cents"]

        price_changed = cart_item.price_at_add_cents != current_price
        price_diff = current_price - cart_item.price_at_add_cents
        product_active = product.is_active

        if price_changed:
            has_price_changes = True
        if not product_active:
            has_unavailable = True

        item_total_at_add = cart_item.price_at_add_cents * cart_item.quantity
        item_total_current = current_price * cart_item.quantity
        total_at_add += item_total_at_add
        total_current += item_total_current

        items.append({
            "id": cart_item.id,
            "product_id": product.id,
            "product_name": product.name,
            "quantity": cart_item.quantity,
            "price_at_add_cents": cart_item.price_at_add_cents,
            "current_price_cents": current_price,
            "price_changed": price_changed,
            "price_diff_cents": price_diff,
            "product_active": product_active,
            "image_url": product.image_url,
            "external_url": product.external_url,
            "max_quantity_per_user": product.max_quantity_per_user,
            "variant_asin": cart_item.variant_asin,
            "variant_value": cart_item.variant_value,
        })

    available_budget = await get_available_budget_cents(db, user_id)

    return {
        "items": items,
        "total_at_add_cents": total_at_add,
        "total_current_cents": total_current,
        "has_price_changes": has_price_changes,
        "has_unavailable_items": has_unavailable,
        "available_budget_cents": available_budget,
        "budget_exceeded": total_current > available_budget,
    }


async def add_to_cart(
    db: AsyncSession, user_id: UUID, product_id: UUID, quantity: int = 1,
    variant_asin: str | None = None,
) -> CartItem:
    if quantity <= 0:
        raise BadRequestError("Quantity must be greater than zero")

    product = await db.get(Product, product_id)
    if not product or not product.is_active or product.archived_at is not None:
        raise BadRequestError("Product not available")

    # Resolve variant info
    price = product.price_cents
    variant_value: str | None = None
    if variant_asin and product.variants:
        matched = next((v for v in product.variants if v.get("asin") == variant_asin), None)
        if not matched:
            raise BadRequestError("Invalid variant")
        if matched.get("price_cents", 0) > 0:
            price = matched["price_cents"]
        variant_value = matched.get("value")

    existing = await db.execute(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
            CartItem.variant_asin == variant_asin,
        ).with_for_update()
    )
    cart_item = existing.scalar_one_or_none()

    # Sum quantity across ALL variants of this product for max_quantity check
    total_result = await db.execute(
        select(func.coalesce(func.sum(CartItem.quantity), 0)).where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
        )
    )
    existing_total: int = total_result.scalar() or 0

    if cart_item:
        # Subtract this variant's current qty since it's included in the total
        new_total = existing_total - cart_item.quantity + cart_item.quantity + quantity
        if new_total > product.max_quantity_per_user:
            raise BadRequestError(
                f"Maximum quantity per user is {product.max_quantity_per_user}"
            )
        cart_item.quantity = cart_item.quantity + quantity
    else:
        if existing_total + quantity > product.max_quantity_per_user:
            raise BadRequestError(
                f"Maximum quantity per user is {product.max_quantity_per_user}"
            )
        cart_item = CartItem(
            user_id=user_id,
            product_id=product_id,
            quantity=quantity,
            price_at_add_cents=price,
            variant_asin=variant_asin,
            variant_value=variant_value,
        )
        db.add(cart_item)

    await db.flush()
    return cart_item


async def update_cart_item(
    db: AsyncSession, user_id: UUID, product_id: UUID, quantity: int
) -> CartItem | None:
    if quantity <= 0:
        raise BadRequestError("Quantity must be greater than zero")

    result = await db.execute(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
        ).with_for_update()
    )
    cart_item = result.scalar_one_or_none()
    if not cart_item:
        return None

    product = await db.get(Product, product_id)
    if product:
        # Sum all other variants of this product to enforce cross-variant limit
        other_result = await db.execute(
            select(func.coalesce(func.sum(CartItem.quantity), 0)).where(
                CartItem.user_id == user_id,
                CartItem.product_id == product_id,
                CartItem.id != cart_item.id,
            )
        )
        other_total: int = other_result.scalar() or 0
        if other_total + quantity > product.max_quantity_per_user:
            raise BadRequestError(
                f"Maximum quantity per user is {product.max_quantity_per_user}"
            )

    cart_item.quantity = quantity
    await db.flush()
    return cart_item


async def remove_from_cart(
    db: AsyncSession, user_id: UUID, product_id: UUID
) -> bool:
    result = await db.execute(
        delete(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
        )
    )
    return result.rowcount > 0


async def clear_cart(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        delete(CartItem).where(CartItem.user_id == user_id)
    )
    return result.rowcount


async def cleanup_stale_items(db: AsyncSession) -> int:
    stale_days = get_setting_int("cart_stale_days") or 30
    cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
    result = await db.execute(
        delete(CartItem).where(CartItem.added_at < cutoff)
    )
    count = result.rowcount
    if count > 0:
        logger.info("Cleaned up %d stale cart items", count)
    return count
