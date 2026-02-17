import logging
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    BadRequestError,
    ConflictError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from src.models.orm.cart_item import CartItem
from src.models.orm.order import Order, OrderItem
from src.models.orm.product import Product
from src.models.orm.user import User
from src.services.budget_service import check_budget_for_order, refresh_budget_cache

logger = logging.getLogger(__name__)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"ordered", "rejected"},
    "ordered": {"delivered", "cancelled"},
    "rejected": set(),
    "delivered": set(),
    "cancelled": set(),
}

BUDGET_RESERVED_STATUSES = {"pending", "ordered", "delivered"}


async def create_order_from_cart(
    db: AsyncSession,
    user_id: UUID,
    delivery_note: str | None = None,
    confirm_price_changes: bool = False,
) -> Order:
    """Create order from cart items with budget check and price validation."""
    result = await db.execute(
        select(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .where(CartItem.user_id == user_id)
    )
    rows = result.all()

    if not rows:
        raise BadRequestError("Cart is empty")

    has_unavailable = any(not p.is_active for _, p in rows)
    if has_unavailable:
        raise BadRequestError(
            "Some items are no longer available. Please remove them from your cart."
        )

    has_price_changes = any(ci.price_at_add_cents != p.price_cents for ci, p in rows)
    if has_price_changes and not confirm_price_changes:
        raise ConflictError(
            "Prices have changed since items were added to cart. "
            "Please confirm the updated prices."
        )

    total_cents = sum(p.price_cents * ci.quantity for ci, p in rows)

    has_budget = await check_budget_for_order(db, user_id, total_cents)
    if not has_budget:
        raise BadRequestError("Insufficient budget for this order")

    order = Order(
        user_id=user_id,
        status="pending",
        total_cents=total_cents,
        delivery_note=delivery_note,
    )
    db.add(order)
    await db.flush()

    for cart_item, product in rows:
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=cart_item.quantity,
            price_cents=product.price_cents,
            external_url=product.external_url,
        )
        db.add(order_item)

    from sqlalchemy import delete
    await db.execute(delete(CartItem).where(CartItem.user_id == user_id))

    await refresh_budget_cache(db, user_id)
    await db.flush()

    return order


async def transition_order(
    db: AsyncSession,
    order_id: UUID,
    new_status: str,
    admin_id: UUID,
    admin_note: str | None = None,
) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found")

    allowed = VALID_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise InvalidStatusTransitionError(
            current=order.status,
            requested=new_status,
            allowed=allowed,
        )

    if new_status == "rejected" and not admin_note:
        raise BadRequestError("Rejection reason is required")

    order.status = new_status
    order.reviewed_by = admin_id
    order.admin_note = admin_note

    from datetime import datetime, timezone
    order.reviewed_at = datetime.now(timezone.utc)

    await db.flush()
    await refresh_budget_cache(db, order.user_id)

    return order


async def get_order_with_items(db: AsyncSession, order_id: UUID) -> dict | None:
    result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        return None

    items_result = await db.execute(
        select(OrderItem, Product.name)
        .join(Product, OrderItem.product_id == Product.id, isouter=True)
        .where(OrderItem.order_id == order_id)
    )

    user = await db.get(User, order.user_id)

    items = []
    for item, product_name in items_result.all():
        items.append({
            "id": item.id,
            "product_id": item.product_id,
            "product_name": product_name,
            "quantity": item.quantity,
            "price_cents": item.price_cents,
            "external_url": item.external_url,
            "vendor_ordered": item.vendor_ordered,
        })

    return {
        "id": order.id,
        "user_id": order.user_id,
        "user_email": user.email if user else None,
        "user_display_name": user.display_name if user else None,
        "status": order.status,
        "total_cents": order.total_cents,
        "delivery_note": order.delivery_note,
        "admin_note": order.admin_note,
        "reviewed_by": order.reviewed_by,
        "reviewed_at": order.reviewed_at,
        "items": items,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


async def get_orders(
    db: AsyncSession,
    *,
    user_id: UUID | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict], int]:
    conditions = []
    if user_id:
        conditions.append(Order.user_id == user_id)
    if status:
        conditions.append(Order.status == status)

    from sqlalchemy import and_
    where = and_(*conditions) if conditions else True

    count_result = await db.execute(
        select(func.count()).select_from(Order).where(where)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Order)
        .where(where)
        .order_by(Order.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    orders = result.scalars().all()

    items = []
    for order in orders:
        order_data = await get_order_with_items(db, order.id)
        if order_data:
            items.append(order_data)

    return items, total


async def update_order_item_check(
    db: AsyncSession, order_item_id: UUID, vendor_ordered: bool
) -> OrderItem | None:
    result = await db.execute(
        select(OrderItem).where(OrderItem.id == order_item_id)
    )
    item = result.scalar_one_or_none()
    if item:
        item.vendor_ordered = vendor_ordered
        await db.flush()
    return item
