import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_, delete, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import (
    BadRequestError,
    ConflictError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from src.core.search import ilike_escape
from src.models.orm.cart_item import CartItem
from src.models.orm.order import Order, OrderInvoice, OrderItem
from src.models.orm.product import Product
from src.models.orm.user import User
from src.notifications.service import notify_staff_email, notify_staff_slack, notify_user_email
from src.mappers.order import order_item_to_dict, invoice_to_dict, order_to_dict
from src.services.budget_service import check_budget_for_order, refresh_budget_cache

logger = logging.getLogger(__name__)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"ordered", "rejected", "cancelled"},
    "ordered": {"delivered", "cancelled"},
    "rejected": set(),
    "delivered": set(),
    "cancelled": set(),
}


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

    def _current_price(ci: CartItem, p: Product) -> int:
        if ci.variant_asin and p.variants:
            for v in p.variants:
                if v.get("asin") == ci.variant_asin and v.get("price_cents", 0) > 0:
                    return v["price_cents"]
        return p.price_cents

    has_price_changes = any(ci.price_at_add_cents != _current_price(ci, p) for ci, p in rows)
    if has_price_changes and not confirm_price_changes:
        raise ConflictError(
            "Prices have changed since items were added to cart. "
            "Please confirm the updated prices."
        )

    total_cents = sum(_current_price(ci, p) * ci.quantity for ci, p in rows)

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
        # Use variant-specific price and URL if applicable
        item_price = product.price_cents
        item_url = product.external_url
        if cart_item.variant_asin:
            if product.variants:
                for v in product.variants:
                    if v.get("asin") == cart_item.variant_asin and v.get("price_cents", 0) > 0:
                        item_price = v["price_cents"]
                        break
            item_url = f"https://www.amazon.de/dp/{cart_item.variant_asin}"

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=cart_item.quantity,
            price_cents=item_price,
            external_url=item_url,
            variant_asin=cart_item.variant_asin,
            variant_value=cart_item.variant_value,
        )
        db.add(order_item)

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
    expected_delivery: str | None = None,
    purchase_url: str | None = None,
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

    if expected_delivery is not None:
        order.expected_delivery = expected_delivery
    if purchase_url is not None:
        order.purchase_url = purchase_url

    order.reviewed_at = datetime.now(timezone.utc)

    await db.flush()
    await refresh_budget_cache(db, order.user_id)

    return order


async def notify_status_changed(
    db: AsyncSession,
    order: Order,
    order_data: dict | None,
    new_status: str,
    admin_note: str | None = None,
) -> None:
    """Send email and Slack notifications after a status change."""
    if order_data and order_data.get("user_email"):
        await notify_user_email(
            order_data["user_email"],
            subject=f"Order Status Updated: {new_status.title()}",
            template_name="order_status_changed.html",
            context={
                "order_id_short": str(order.id)[:8],
                "new_status": new_status,
                "admin_note": admin_note,
                "items": order_data.get("items", []),
                "total_cents": order.total_cents,
            },
        )

    if new_status == "cancelled":
        await notify_staff_slack(
            db, event="order.cancelled",
            text=f"Order {str(order.id)[:8]} has been cancelled.",
        )
    else:
        await notify_staff_slack(
            db, event="order.status_changed",
            text=f"Order {str(order.id)[:8]} status changed to {new_status}.",
        )


async def notify_order_created(
    db: AsyncSession,
    order: Order,
    user: User,
    order_data: dict | None,
) -> None:
    """Send email and Slack notifications after a new order is created."""
    from src.core.config import settings as _settings
    await notify_staff_email(
        db, event="order.created",
        subject=f"New Order from {user.display_name}",
        template_name="order_created.html",
        context={
            "user_name": user.display_name,
            "user_email": user.email,
            "items": order_data["items"] if order_data else [],
            "total_cents": order.total_cents,
            "delivery_note": order.delivery_note,
            "admin_url": f"{_settings.frontend_url}/admin/orders/{order.id}",
        },
    )
    await notify_staff_slack(
        db, event="order.created",
        text=f"New order from {user.display_name} ({user.email}) - Total: EUR {order.total_cents / 100:.2f}",
    )


async def notify_order_cancelled_by_user(
    db: AsyncSession,
    order: Order,
    user: User,
    reason: str,
) -> None:
    """Send email and Slack notifications after a user cancels their order."""
    await notify_staff_email(
        db, event="order.cancelled",
        subject=f"Order Cancelled by {user.display_name}",
        template_name="order_cancelled.html",
        context={
            "user_name": user.display_name,
            "user_email": user.email,
            "order_id": str(order.id),
            "reason": reason,
            "total_cents": order.total_cents,
        },
    )
    await notify_staff_slack(
        db, event="order.cancelled",
        text=f"Order #{str(order.id)[:8]} cancelled by {user.display_name}: {reason}",
    )



async def cancel_order_by_user(
    db: AsyncSession,
    order_id: UUID,
    user_id: UUID,
    reason: str,
) -> Order:
    """Cancel a pending order by the owning user."""
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found")

    if order.user_id != user_id:
        raise NotFoundError("Order not found")

    if order.status != "pending":
        raise BadRequestError("Only pending orders can be cancelled")

    order.status = "cancelled"
    order.cancellation_reason = reason
    order.cancelled_by = user_id
    order.cancelled_at = datetime.now(timezone.utc)

    await db.flush()
    await refresh_budget_cache(db, order.user_id)

    return order


async def get_order_with_items(
    db: AsyncSession, order_id: UUID, *, include_invoices: bool = False
) -> dict | None:
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

    items = [
        order_item_to_dict(item, product_name)
        for item, product_name in items_result.all()
    ]

    invoices: list[dict] = []
    if include_invoices:
        inv_result = await db.execute(
            select(OrderInvoice)
            .where(OrderInvoice.order_id == order_id)
            .order_by(OrderInvoice.uploaded_at.desc())
        )
        invoices = [invoice_to_dict(inv) for inv in inv_result.scalars().all()]

    return order_to_dict(order, user, items, invoices)


async def get_orders(
    db: AsyncSession,
    *,
    user_id: UUID | None = None,
    status: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    page: int = 1,
    per_page: int = 20,
    include_invoices: bool = False,
) -> tuple[list[dict], int]:
    conditions = []
    if user_id:
        conditions.append(Order.user_id == user_id)
    if status:
        conditions.append(Order.status == status)

    # Text search: filter by user name, email, or order ID prefix
    if q:
        search_term = ilike_escape(q)
        # Subquery to find matching user IDs
        user_subq = select(User.id).where(
            or_(
                User.display_name.ilike(search_term),
                User.email.ilike(search_term),
            )
        ).scalar_subquery()
        conditions.append(
            or_(
                Order.user_id.in_(user_subq),
                func.cast(Order.id, sa.String).ilike(search_term),
            )
        )

    where = and_(*conditions) if conditions else True

    count_result = await db.execute(
        select(func.count()).select_from(Order).where(where)
    )
    total = count_result.scalar() or 0

    # Sorting
    order_clause = Order.created_at.desc()  # default: newest
    if sort == "oldest":
        order_clause = Order.created_at.asc()
    elif sort == "total_asc":
        order_clause = Order.total_cents.asc()
    elif sort == "total_desc":
        order_clause = Order.total_cents.desc()

    query = (
        select(Order)
        .options(selectinload(Order.items))
        .where(where)
        .order_by(order_clause)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    if include_invoices:
        query = query.options(selectinload(Order.invoices))

    result = await db.execute(query)
    orders = result.scalars().unique().all()

    # Batch-fetch product names and user info
    order_user_ids = {o.user_id for o in orders}
    product_ids = {item.product_id for o in orders for item in o.items}

    users_map: dict[UUID, User] = {}
    if order_user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(order_user_ids))
        )
        users_map = {u.id: u for u in users_result.scalars().all()}

    product_names: dict[UUID, str] = {}
    if product_ids:
        prod_result = await db.execute(
            select(Product.id, Product.name).where(Product.id.in_(product_ids))
        )
        product_names = {pid: pname for pid, pname in prod_result.all()}

    result_list = []
    for order in orders:
        user = users_map.get(order.user_id)
        order_items = [
            order_item_to_dict(item, product_names.get(item.product_id))
            for item in order.items
        ]
        invoices = (
            [invoice_to_dict(inv) for inv in order.invoices]
            if include_invoices
            else []
        )
        result_list.append(order_to_dict(order, user, order_items, invoices))

    return result_list, total


async def update_order_item_check(
    db: AsyncSession, order_id: UUID, order_item_id: UUID, vendor_ordered: bool
) -> OrderItem | None:
    # Validate order is in a modifiable status
    order_result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found")
    if order.status not in ("pending", "ordered", "delivered"):
        raise BadRequestError("Cannot modify items on a rejected or cancelled order")

    result = await db.execute(
        select(OrderItem).where(
            OrderItem.id == order_item_id,
            OrderItem.order_id == order_id,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        item.vendor_ordered = vendor_ordered
        await db.flush()
    return item


async def update_purchase_url(
    db: AsyncSession, order_id: UUID, purchase_url: str | None
) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found")
    order.purchase_url = purchase_url
    await db.flush()
    return order


async def add_invoice(
    db: AsyncSession,
    order_id: UUID,
    filename: str,
    file_path: str,
    uploaded_by: UUID,
) -> OrderInvoice:
    # Verify order exists
    order_result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    if not order_result.scalar_one_or_none():
        raise NotFoundError("Order not found")

    invoice = OrderInvoice(
        order_id=order_id,
        filename=filename,
        file_path=file_path,
        uploaded_by=uploaded_by,
    )
    db.add(invoice)
    await db.flush()
    return invoice


async def get_invoice(
    db: AsyncSession, order_id: UUID, invoice_id: UUID
) -> OrderInvoice:
    """Retrieve an invoice record with path traversal validation."""
    result = await db.execute(
        select(OrderInvoice).where(
            OrderInvoice.id == invoice_id,
            OrderInvoice.order_id == order_id,
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Invoice not found")

    from src.core.config import settings as _settings
    file_path = Path(invoice.file_path).resolve()
    upload_root = _settings.upload_dir.resolve()

    if not file_path.is_relative_to(upload_root):
        raise BadRequestError("Invalid file path")

    if not file_path.exists():
        raise NotFoundError("Invoice file not found on disk")

    return invoice


async def delete_invoice(
    db: AsyncSession, order_id: UUID, invoice_id: UUID
) -> str:
    """Delete invoice DB record and return file_path for cleanup."""
    result = await db.execute(
        select(OrderInvoice).where(
            OrderInvoice.id == invoice_id,
            OrderInvoice.order_id == order_id,
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Invoice not found")

    file_path = Path(invoice.file_path).resolve()
    await db.delete(invoice)
    await db.flush()

    # Clean up file on disk (with path traversal protection)
    from src.core.config import settings
    upload_root = settings.upload_dir.resolve()
    if file_path.is_relative_to(upload_root) and file_path.exists():
        await asyncio.to_thread(file_path.unlink)

    return str(file_path)
