import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.hibob.client import HiBobClient, HiBobClientProtocol
from src.models.orm.order import Order, OrderItem
from src.models.orm.product import Product
from src.models.orm.user import User
from src.services.settings_service import get_setting, load_settings

logger = logging.getLogger(__name__)


async def unsync_order_from_hibob(
    db: AsyncSession,
    order_id: UUID,
    admin_id: UUID,
    client: HiBobClientProtocol | None = None,
) -> int:
    """Remove order entries from HiBob and reset sync status.

    Returns the number of entries deleted.
    Raises ValueError on validation failures.
    """
    if client is None:
        client = HiBobClient()

    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise ValueError("Order not found")

    if order.hibob_synced_at is None:
        raise ValueError("Order is not synced to HiBob")

    user = await db.get(User, order.user_id)
    if not user or not user.hibob_id:
        raise ValueError("User has no HiBob ID linked")

    await load_settings(db)
    table_id = get_setting("hibob_purchase_table_id")
    if not table_id:
        raise ValueError("HiBob purchase table not configured")

    col_description = get_setting("hibob_purchase_col_description")

    # Load order items with product names to match against HiBob entries
    items_result = await db.execute(
        select(OrderItem, Product.name)
        .join(Product, OrderItem.product_id == Product.id, isouter=True)
        .where(OrderItem.order_id == order_id)
    )
    items = items_result.all()

    # Build expected descriptions to match HiBob entries
    expected_descriptions = set()
    for item, product_name in items:
        desc = product_name or "Product"
        if item.variant_value:
            desc = f"{desc} ({item.variant_value})"
        expected_descriptions.add(desc)

    # Fetch current entries from HiBob
    entries = await client.get_custom_table(user.hibob_id, table_id)

    # Find matching entries by description
    entries_to_delete = [
        e for e in entries
        if e.get(col_description) in expected_descriptions
    ]

    if not entries_to_delete:
        logger.warning(
            "No matching HiBob entries found for order %s (expected: %s, found: %s)",
            order_id, expected_descriptions, [e.get(col_description) for e in entries],
        )

    # Delete matching entries from HiBob
    deleted = 0
    for i, entry in enumerate(entries_to_delete):
        entry_id = str(entry["id"])
        await client.delete_custom_table_entry(user.hibob_id, table_id, entry_id)
        deleted += 1
        if i < len(entries_to_delete) - 1:
            await asyncio.sleep(1.5)

    # Reset sync status in DB
    order.hibob_synced_at = None
    order.hibob_synced_by = None

    for item, _ in items:
        item.hibob_synced = False

    await db.flush()
    return deleted


async def sync_order_to_hibob(
    db: AsyncSession,
    order_id: UUID,
    admin_id: UUID,
    client: HiBobClientProtocol | None = None,
) -> int:
    """Push order items to the employee's HiBob custom table.

    Returns the number of entries created.
    Raises ValueError on validation failures.

    Uses SELECT FOR UPDATE to prevent concurrent syncs and tracks
    per-item sync status so a retry after partial failure only
    sends the remaining items.
    """
    if client is None:
        client = HiBobClient()

    # Lock the order row to prevent concurrent syncs
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise ValueError("Order not found")

    if order.status != "delivered":
        raise ValueError("Only delivered orders can be synced to HiBob")

    if order.hibob_synced_at is not None:
        raise ValueError("Order already synced to HiBob")

    user = await db.get(User, order.user_id)
    if not user or not user.hibob_id:
        raise ValueError("User has no HiBob ID linked")

    # Load settings
    await load_settings(db)
    table_id = get_setting("hibob_purchase_table_id")
    if not table_id:
        raise ValueError("HiBob purchase table not configured (hibob_purchase_table_id)")

    col_date = get_setting("hibob_purchase_col_date")
    col_description = get_setting("hibob_purchase_col_description")
    col_amount = get_setting("hibob_purchase_col_amount")

    # Load order items with product names
    items_result = await db.execute(
        select(OrderItem, Product.name)
        .join(Product, OrderItem.product_id == Product.id, isouter=True)
        .where(OrderItem.order_id == order_id)
    )
    items = items_result.all()

    if not items:
        raise ValueError("Order has no items")

    # Filter out items already synced (from a previous partial attempt)
    pending_items = [(item, name) for item, name in items if not item.hibob_synced]
    if not pending_items:
        # All items were already synced in a previous partial run — just finalise
        order.hibob_synced_at = datetime.now(timezone.utc)
        order.hibob_synced_by = admin_id
        await db.flush()
        return 0

    # Determine the entry date (delivery date or today)
    entry_date = (order.reviewed_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")

    entries_created = 0
    for i, (item, product_name) in enumerate(pending_items):
        description = product_name or "Product"
        if item.variant_value:
            description = f"{description} ({item.variant_value})"

        amount_value = round(item.price_cents * item.quantity / 100, 2)

        entry = {
            col_date: entry_date,
            col_description: description,
            col_amount: {
                "value": amount_value,
                "currency": "EUR",
            },
        }

        await client.create_custom_table_entry(user.hibob_id, table_id, entry)

        # Mark this item as synced immediately so a partial failure
        # won't re-send it on retry
        item.hibob_synced = True
        await db.flush()
        entries_created += 1

        # Rate limit: 1.5s delay between items (avoid HiBob rate limits)
        if i < len(pending_items) - 1:
            await asyncio.sleep(1.5)

    # All items synced — mark order as fully synced
    order.hibob_synced_at = datetime.now(timezone.utc)
    order.hibob_synced_by = admin_id
    await db.flush()

    return entries_created
