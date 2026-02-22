import asyncio
import logging
import uuid as _uuid
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import and_, delete, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.core.exceptions import (
    BadRequestError,
    ConflictError,
    InvalidStatusTransitionError,
    NotFoundError,
)
from src.core.file_validation import ALLOWED_INVOICE_EXTENSIONS, ALLOWED_INVOICE_TYPES, MAX_INVOICE_SIZE, validate_file_magic
from src.core.search import ilike_escape
from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.cart_item import CartItem
from src.models.orm.order import Order, OrderInvoice, OrderItem, OrderTrackingUpdate
from src.models.orm.product import Product
from src.models.orm.user import User
from src.notifications.service import notify_staff_email, notify_user_email
from src.mappers.order import order_item_to_dict, invoice_to_dict, order_to_dict, tracking_update_to_dict
from src.services.budget_service import check_budget_for_order, get_live_spent_cents, get_live_adjustment_cents, refresh_budget_cache
from src.services.settings_service import get_setting_int

logger = logging.getLogger(__name__)


async def _retry_notification(coro_factory, order_id: str, max_attempts: int = 3):
    """Retry a notification coroutine with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            await coro_factory()
            return
        except Exception:
            if attempt == max_attempts - 1:
                logger.exception("Notification failed after %d attempts for order %s", max_attempts, order_id)
            else:
                await asyncio.sleep(2 ** attempt)


VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"ordered", "rejected", "cancelled"},
    "ordered": {"delivered", "cancelled"},
    "rejected": set(),
    "delivered": {"return_requested"},
    "cancelled": set(),
    "return_requested": {"returned", "delivered"},
    "returned": set(),
}

async def create_order_from_cart(
    db: AsyncSession,
    user_id: UUID,
    delivery_note: str | None = None,
    confirm_price_changes: bool = False,
    idempotency_key: str | None = None,
) -> Order:
    """Create order from cart items with budget check and price validation."""
    # Idempotency: if a key was provided, check for an existing order
    if idempotency_key:
        existing_result = await db.execute(
            select(Order).where(
                Order.user_id == user_id,
                Order.idempotency_key == idempotency_key,
            )
        )
        existing_order = existing_result.scalar_one_or_none()
        if existing_order:
            return existing_order

    result = await db.execute(
        select(CartItem, Product)
        .join(Product, CartItem.product_id == Product.id)
        .where(CartItem.user_id == user_id)
        .with_for_update()
    )
    rows = result.all()

    if not rows:
        raise BadRequestError("Cart is empty")

    has_unavailable = any(not p.is_active or p.archived_at is not None for _, p in rows)
    if has_unavailable:
        raise BadRequestError(
            "Some items are no longer available. Please remove them from your cart."
        )

    def _current_price(ci: CartItem, p: Product) -> int:
        if ci.variant_asin:
            if p.variants:
                for v in p.variants:
                    if v.get("asin") == ci.variant_asin and v.get("price_cents", 0) > 0:
                        return v["price_cents"]
            # Variant was in cart but is no longer available in product
            raise BadRequestError(
                f"Variant {ci.variant_asin} is no longer available for {p.name}. "
                "Please remove it from your cart."
            )
        return p.price_cents

    has_price_changes = any(ci.price_at_add_cents != _current_price(ci, p) for ci, p in rows)
    if has_price_changes and not confirm_price_changes:
        raise ConflictError(
            "Prices have changed since items were added to cart. "
            "Please confirm the updated prices."
        )

    # Stock validation: check if any product has insufficient stock
    for cart_item, product in rows:
        if product.stock_quantity is not None:
            if cart_item.quantity > product.stock_quantity:
                raise BadRequestError(
                    f"Insufficient stock for {product.name}. "
                    f"Available: {product.stock_quantity}, requested: {cart_item.quantity}"
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
        idempotency_key=idempotency_key,
    )
    db.add(order)

    for cart_item, product in rows:
        # _current_price already validated variant availability above
        item_price = _current_price(cart_item, product)
        item_url = product.external_url
        if cart_item.variant_asin:
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

    # Decrement stock for products that track stock
    for cart_item, product in rows:
        if product.stock_quantity is not None:
            product.stock_quantity = product.stock_quantity - cart_item.quantity

    await db.execute(delete(CartItem).where(CartItem.user_id == user_id))

    await db.flush()  # single atomic flush: order + items + cart deletion
    await refresh_budget_cache(db, user_id)

    return order


async def transition_order(
    db: AsyncSession,
    order_id: UUID,
    new_status: str,
    admin_id: UUID,
    admin_note: str | None = None,
    expected_delivery: str | None = None,
    purchase_url: str | None = None,
    tracking_number: str | None = None,
    tracking_url: str | None = None,
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
    if tracking_number is not None:
        order.tracking_number = tracking_number
    if tracking_url is not None:
        order.tracking_url = tracking_url

    order.reviewed_at = datetime.now(timezone.utc)

    # Handle return: refund budget and restore stock
    if new_status == "returned":
        # Create a positive budget adjustment to refund the order total
        order_id_short = str(order.id)[:8]
        refund = BudgetAdjustment(
            user_id=order.user_id,
            amount_cents=order.total_cents,
            reason=f"Return: Order #{order_id_short}",
            created_by=admin_id,
            source="return",
        )
        db.add(refund)

        # Restore stock for products that track stock
        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        order_items = items_result.scalars().all()
        product_ids = {item.product_id for item in order_items}
        if product_ids:
            prod_result = await db.execute(
                select(Product).where(Product.id.in_(product_ids)).with_for_update()
            )
            products_map = {p.id: p for p in prod_result.scalars().all()}
            for item in order_items:
                product = products_map.get(item.product_id)
                if product and product.stock_quantity is not None:
                    product.stock_quantity = product.stock_quantity + item.quantity

    # Handle cancelled/rejected: restore stock
    if new_status in ("cancelled", "rejected"):
        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        order_items = items_result.scalars().all()
        product_ids = {item.product_id for item in order_items}
        if product_ids:
            prod_result = await db.execute(
                select(Product).where(Product.id.in_(product_ids)).with_for_update()
            )
            products_map = {p.id: p for p in prod_result.scalars().all()}
            for item in order_items:
                product = products_map.get(item.product_id)
                if product and product.stock_quantity is not None:
                    product.stock_quantity = product.stock_quantity + item.quantity

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
    """Send email notifications after a status change."""
    if not order_data or not order_data.get("user_email"):
        return

    user_email = order_data["user_email"]
    items = order_data.get("items", [])

    # Send status-specific notifications to the employee
    if new_status == "ordered":
        await notify_user_email(
            user_email,
            subject="Your order has been placed with the vendor",
            template_name="order_shipped.html",
            context={
                "order_id_short": str(order.id)[:8],
                "expected_delivery": order.expected_delivery,
                "items": items,
                "total_cents": order.total_cents,
            },
        )
    elif new_status == "delivered":
        await notify_user_email(
            user_email,
            subject="Your order has been delivered",
            template_name="order_delivered.html",
            context={
                "order_id_short": str(order.id)[:8],
                "items": items,
                "total_cents": order.total_cents,
            },
        )

    # Always send the generic status-change notification as well
    await notify_user_email(
        user_email,
        subject=f"Order Status Updated: {new_status.title()}",
        template_name="order_status_changed.html",
        context={
            "order_id_short": str(order.id)[:8],
            "new_status": new_status,
            "admin_note": admin_note,
            "items": items,
            "total_cents": order.total_cents,
        },
    )


async def notify_order_created(
    db: AsyncSession,
    order: Order,
    user: User,
    order_data: dict | None,
) -> None:
    """Send email notifications after a new order is created."""
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


async def check_and_notify_budget_warning(
    db: AsyncSession,
    user: User,
) -> None:
    """Send a budget warning email if the user's budget usage exceeds the threshold."""
    from src.audit.models import AuditLog
    from src.audit.service import write_audit_log

    threshold = get_setting_int("budget_warning_threshold_percent")
    if threshold <= 0 or threshold > 100:
        return

    total_budget = user.total_budget_cents
    if total_budget <= 0:
        return

    spent = await get_live_spent_cents(db, user.id)
    adjustments = await get_live_adjustment_cents(db, user.id)
    effective_total = total_budget + adjustments
    if effective_total <= 0:
        return

    remaining = max(0, effective_total - spent)
    percent_used = round((spent / effective_total) * 100)

    if percent_used >= threshold:
        # Dedup: check if a budget_warning_sent audit entry exists for this user
        # in the current month. If so, skip sending.
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        dedup_result = await db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.user_id == user.id,
                AuditLog.action == "budget_warning_sent",
                AuditLog.created_at >= month_start,
            )
        )
        already_sent = (dedup_result.scalar() or 0) > 0
        if already_sent:
            return

        await notify_user_email(
            user.email,
            subject=f"Budget Warning \u2014 {threshold}% Used",
            template_name="budget_warning.html",
            context={
                "threshold_percent": threshold,
                "percent_used": percent_used,
                "spent_cents": spent,
                "remaining_cents": remaining,
                "total_budget_cents": effective_total,
            },
        )

        # Record that we sent the warning so it won't be sent again this month
        await write_audit_log(
            db,
            user_id=user.id,
            action="budget_warning_sent",
            resource_type="budget",
            details={
                "threshold_percent": threshold,
                "percent_used": percent_used,
                "spent_cents": spent,
                "total_budget_cents": effective_total,
            },
        )


async def notify_order_cancelled_by_user(
    db: AsyncSession,
    order: Order,
    user: User,
    reason: str,
) -> None:
    """Send email notifications after a user cancels their order."""
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

    # Notify the employee themselves as confirmation
    await notify_user_email(
        user.email,
        subject=f"Order Status Updated: Cancelled",
        template_name="order_status_changed.html",
        context={
            "order_id_short": str(order.id)[:8],
            "new_status": "cancelled",
            "admin_note": reason,
            "items": [],
            "total_cents": order.total_cents,
        },
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

    # Restore stock for products that track stock
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    order_items = items_result.scalars().all()
    product_ids = {item.product_id for item in order_items}
    if product_ids:
        prod_result = await db.execute(
            select(Product).where(Product.id.in_(product_ids)).with_for_update()
        )
        products_map = {p.id: p for p in prod_result.scalars().all()}
        for item in order_items:
            product = products_map.get(item.product_id)
            if product and product.stock_quantity is not None:
                product.stock_quantity = product.stock_quantity + item.quantity

    await db.flush()  # single atomic flush: status change + stock restore
    await refresh_budget_cache(db, order.user_id)

    return order


async def get_order_with_items(
    db: AsyncSession,
    order_id: UUID,
    *,
    include_invoices: bool = False,
    include_tracking_updates: bool = False,
) -> dict | None:
    # Build a single query: fetch order + user (joined) with eager-loaded items
    query = (
        select(Order, User)
        .join(User, Order.user_id == User.id, isouter=True)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    if include_invoices:
        query = query.options(selectinload(Order.invoices))
    if include_tracking_updates:
        query = query.options(selectinload(Order.tracking_updates))

    result = await db.execute(query)
    row = result.unique().first()
    if not row:
        return None

    order, user = row.tuple()

    # Batch-fetch product names for order items
    product_ids = {item.product_id for item in order.items}
    product_names: dict[UUID, str] = {}
    if product_ids:
        prod_result = await db.execute(
            select(Product.id, Product.name).where(Product.id.in_(product_ids))
        )
        product_names = {pid: pname for pid, pname in prod_result.all()}

    items = [
        order_item_to_dict(item, product_names.get(item.product_id))
        for item in order.items
    ]

    invoices: list[dict] = []
    if include_invoices:
        invoices = [
            invoice_to_dict(inv)
            for inv in sorted(order.invoices, key=lambda i: i.uploaded_at, reverse=True)
        ]

    tracking_updates: list[dict] = []
    if include_tracking_updates:
        updates = sorted(order.tracking_updates, key=lambda u: u.created_at, reverse=True)
        # Batch-fetch creator names
        creator_ids = {u.created_by for u in updates}
        creators_map: dict[UUID, str] = {}
        if creator_ids:
            creators_result = await db.execute(
                select(User.id, User.display_name).where(User.id.in_(creator_ids))
            )
            creators_map = {uid: name for uid, name in creators_result.all()}
        tracking_updates = [
            tracking_update_to_dict(u, creators_map.get(u.created_by))
            for u in updates
        ]

    return order_to_dict(order, user, items, invoices, tracking_updates)


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
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[dict], int]:
    conditions = []
    if user_id:
        conditions.append(Order.user_id == user_id)
    if status:
        conditions.append(Order.status == status)
    if date_from:
        conditions.append(Order.created_at >= date_from)
    if date_to:
        conditions.append(Order.created_at <= date_to)

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
        select(Order).where(Order.id == order_id).with_for_update()
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


async def update_tracking_info(
    db: AsyncSession,
    order_id: UUID,
    admin_id: UUID,
    tracking_number: str | None = None,
    tracking_url: str | None = None,
    comment: str | None = None,
) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found")

    if order.status not in ("ordered", "delivered"):
        raise BadRequestError("Tracking info can only be updated for ordered or delivered orders")

    tracking_number_changed = (
        tracking_number is not None and tracking_number != order.tracking_number
    )

    if tracking_number is not None:
        order.tracking_number = tracking_number
    if tracking_url is not None:
        order.tracking_url = tracking_url

    if comment:
        update = OrderTrackingUpdate(
            order_id=order_id,
            comment=comment,
            created_by=admin_id,
        )
        db.add(update)

    await db.flush()

    # Register with AfterShip if tracking number was set/changed
    if tracking_number_changed and tracking_number:
        try:
            await _register_aftership_tracking(db, order)
        except Exception:
            logger.exception("Failed to register AfterShip tracking for order %s", order_id)

    return order


async def _register_aftership_tracking(db: AsyncSession, order: Order) -> None:
    """Register a tracking number with AfterShip for automated status updates."""
    from src.integrations.aftership.client import (
        CARRIER_SLUG_MAP,
        aftership_client,
    )

    if not aftership_client.is_configured:
        return
    if not order.tracking_number:
        return

    # Try to detect the carrier slug
    slug = order.aftership_slug
    if not slug:
        # Use frontend's carrier detection logic (duplicated here for backend)
        slug = _detect_aftership_slug(order.tracking_number)

    tracking = await aftership_client.create_tracking(
        tracking_number=order.tracking_number,
        slug=slug,
        order_id=str(order.id),
    )

    if tracking:
        order.aftership_tracking_id = tracking.id
        order.aftership_slug = tracking.slug
        await db.flush()
        logger.info(
            "Registered AfterShip tracking for order %s: id=%s slug=%s",
            order.id, tracking.id, tracking.slug,
        )


def _detect_aftership_slug(tracking_number: str) -> str | None:
    """Detect AfterShip courier slug from tracking number format."""
    import re

    tn = tracking_number.strip()
    patterns: list[tuple[str, str]] = [
        (r"^DE\d{10}$", "swiship"),
        (r"^TB[ACM]\d{12}$", "amazon"),
        (r"^1Z[A-Z0-9]{16}$", "ups"),
        (r"^JJD\d{18,20}$", "dhl"),
        (r"^\d{12,20}$", "dhl-germany"),
        (r"^\d{14,15}$", "dpd-de"),
        (r"^\d{16}$", "hermes-de"),
        (r"^[A-Z0-9]{11,12}$", "gls"),
    ]
    for pattern, slug in patterns:
        if re.match(pattern, tn, re.IGNORECASE):
            return slug
    return None


async def notify_tracking_update(
    db: AsyncSession,
    order: Order,
    order_data: dict | None,
    comment: str | None = None,
) -> None:
    """Send email notification for a tracking update."""
    if order_data and order_data.get("user_email"):
        await notify_user_email(
            order_data["user_email"],
            subject=f"Tracking Update for Order #{str(order.id)[:8]}",
            template_name="order_tracking_update.html",
            context={
                "order_id_short": str(order.id)[:8],
                "tracking_number": order.tracking_number,
                "tracking_url": order.tracking_url,
                "comment": comment,
                "items": order_data.get("items", []),
                "total_cents": order.total_cents,
            },
        )


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


async def upload_invoice(
    db: AsyncSession,
    order_id: UUID,
    filename: str,
    content: bytes,
    content_type: str | None,
    uploader_id: UUID,
) -> OrderInvoice:
    """Validate, store, and record an invoice file for an order.

    Handles file-type validation, size checks, directory creation,
    disk writes, and DB record creation.
    """
    from src.core.config import settings as _settings

    # Validate file type
    if content_type not in ALLOWED_INVOICE_TYPES:
        raise BadRequestError("Invalid file type. Allowed: PDF, JPEG, PNG")

    # Validate magic bytes match claimed content type
    if not validate_file_magic(content, content_type):
        raise BadRequestError("File content does not match declared content type")

    # Validate extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_INVOICE_EXTENSIONS:
        raise BadRequestError(
            f"Invalid file extension. Allowed: {', '.join(ALLOWED_INVOICE_EXTENSIONS)}"
        )

    # Validate file size
    if len(content) > MAX_INVOICE_SIZE:
        raise BadRequestError(
            f"File too large. Maximum size is {MAX_INVOICE_SIZE // (1024 * 1024)} MB"
        )

    # Create directory
    invoice_dir = _settings.upload_dir / "invoices" / str(order_id)
    invoice_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    stored_name = f"{_uuid.uuid4()}{ext}"
    file_path = invoice_dir / stored_name

    # Write file (non-blocking)
    await asyncio.to_thread(file_path.write_bytes, content)

    # Create DB record
    invoice = await add_invoice(db, order_id, filename, str(file_path), uploader_id)
    return invoice
