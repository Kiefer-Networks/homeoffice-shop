"""AfterShip tracking sync — batch sync 4x daily (08, 12, 16, 20 UTC) and manual admin sync."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit.service import write_audit_log
from src.core.database import async_session_factory
from src.integrations.aftership.client import (
    AFTERSHIP_TAG_TO_STATUS,
    AfterShipTracking,
    aftership_client,
)
from src.mappers.order import order_item_to_dict
from src.models.orm.order import Order, OrderItem, OrderTrackingUpdate
from src.models.orm.product import Product
from src.models.orm.user import User
from src.notifications.service import notify_user_email
from src.services.budget_service import refresh_budget_cache

logger = logging.getLogger(__name__)


async def _load_order_items(db: AsyncSession, order_id) -> list[dict]:
    """Load order items with product names for email context."""
    result = await db.execute(
        select(OrderItem, Product.name)
        .join(Product, OrderItem.product_id == Product.id, isouter=True)
        .where(OrderItem.order_id == order_id)
    )
    return [order_item_to_dict(item, name) for item, name in result.all()]


async def _notify_and_audit_delivery(
    db: AsyncSession,
    order: Order,
    tracking: AfterShipTracking,
) -> None:
    """Send delivery email to employee and write audit log entry."""
    user = await db.get(User, order.user_id)
    items = await _load_order_items(db, order.id)

    # Email notification to employee
    if user:
        try:
            await notify_user_email(
                user.email,
                subject=f"Your order #{str(order.id)[:8]} has been delivered!",
                template_name="order_status_changed.html",
                context={
                    "order_id_short": str(order.id)[:8],
                    "new_status": "delivered",
                    "admin_note": "Automatically confirmed via carrier tracking.",
                    "items": items,
                    "total_cents": order.total_cents,
                },
            )
        except Exception:
            logger.exception("Failed to send delivery notification for order %s", order.id)

    # Audit log
    await write_audit_log(
        db,
        user_id=order.user_id,
        action="aftership.auto_delivered",
        resource_type="order",
        resource_id=order.id,
        details={
            "tracking_number": order.tracking_number,
            "tracking_url": order.tracking_url,
            "aftership_tracking_id": order.aftership_tracking_id,
            "aftership_slug": order.aftership_slug,
            "aftership_tag": tracking.tag,
            "aftership_subtag": tracking.subtag_message,
            "carrier_checkpoint": (
                tracking.checkpoints[-1].get("message") if tracking.checkpoints else None
            ),
            "order_total_cents": order.total_cents,
            "order_user_email": user.email if user else None,
            "order_user_name": user.display_name if user else None,
            "items": [
                {"product_name": i.get("product_name"), "quantity": i.get("quantity")}
                for i in items
            ],
        },
    )


async def _apply_tracking_update(
    db: AsyncSession,
    order: Order,
    tracking: AfterShipTracking,
) -> bool:
    """Apply a fetched AfterShip tracking result to an order.

    Creates a timeline entry, auto-transitions to delivered if applicable,
    sends email notification, and writes audit log.
    Returns True if order was transitioned to delivered.
    """
    new_status = AFTERSHIP_TAG_TO_STATUS.get(tracking.tag)

    status_msg = f"AfterShip: {tracking.subtag_message}"
    if tracking.checkpoints:
        latest = tracking.checkpoints[-1]
        location = latest.get("location", "")
        message = latest.get("message", "")
        if location and message:
            status_msg = f"AfterShip: {message} ({location})"
        elif message:
            status_msg = f"AfterShip: {message}"

    # Deduplicate — skip if we already logged this exact message
    existing = await db.execute(
        select(OrderTrackingUpdate)
        .where(
            OrderTrackingUpdate.order_id == order.id,
            OrderTrackingUpdate.comment == status_msg,
        )
        .limit(1)
    )
    if existing.scalar_one_or_none():
        return False

    # Add tracking timeline entry
    update = OrderTrackingUpdate(
        order_id=order.id,
        comment=status_msg,
        created_by=order.user_id,
    )
    db.add(update)

    # Update tracking URL if AfterShip provides a better one
    if tracking.tracking_url and tracking.tracking_url != order.tracking_url:
        order.tracking_url = tracking.tracking_url

    transitioned = False

    # Auto-transition to delivered
    if new_status == "delivered" and order.status == "ordered":
        order.status = "delivered"
        order.reviewed_at = datetime.now(timezone.utc)
        transitioned = True
        logger.info("Order %s auto-transitioned to delivered via AfterShip", order.id)

        await refresh_budget_cache(db, order.user_id)
        await _notify_and_audit_delivery(db, order, tracking)

    await db.flush()
    return transitioned


async def sync_order_tracking(db: AsyncSession, order: Order) -> bool:
    """Check AfterShip for status updates on a single order (manual admin sync).

    Makes 1 API call. Returns True if order was auto-transitioned to delivered.
    """
    if not order.aftership_tracking_id:
        return False

    tracking = await aftership_client.get_tracking_by_id(order.aftership_tracking_id)
    if not tracking:
        return False

    return await _apply_tracking_update(db, order, tracking)


async def sync_all_active_orders() -> dict:
    """Batch-sync all orders via a single AfterShip list call.

    Fetches ALL trackings in 1 API call, then matches against our database.
    Returns summary stats.
    """
    if not aftership_client.is_configured:
        return {"skipped": True}

    # 1) One API call to fetch ALL trackings from AfterShip
    all_trackings = await aftership_client.get_all_trackings()
    if not all_trackings:
        return {"checked": 0, "delivered": 0, "api_calls": 1}

    # Index by AfterShip ID for fast lookup
    tracking_map = {t.id: t for t in all_trackings}

    async with async_session_factory() as db:
        # 2) Find our orders that have AfterShip tracking and are still "ordered"
        result = await db.execute(
            select(Order).where(
                Order.status == "ordered",
                Order.aftership_tracking_id.isnot(None),
            )
        )
        orders = result.scalars().all()

        if not orders:
            return {"checked": 0, "delivered": 0, "api_calls": 1}

        logger.info(
            "AfterShip batch sync: %d trackings fetched, %d active orders to check",
            len(all_trackings), len(orders),
        )

        # 3) Match and process — no additional API calls
        delivered_count = 0
        delivered_order_ids: list[str] = []
        for order in orders:
            tracking = tracking_map.get(order.aftership_tracking_id)
            if not tracking:
                continue
            try:
                if await _apply_tracking_update(db, order, tracking):
                    delivered_count += 1
                    delivered_order_ids.append(str(order.id)[:8])
            except Exception:
                logger.exception("AfterShip sync failed for order %s", order.id)

        # Audit log for the batch sync run itself
        await write_audit_log(
            db,
            user_id=orders[0].user_id,  # attribute to first order's user
            action="aftership.batch_sync",
            resource_type="system",
            details={
                "trackings_fetched": len(all_trackings),
                "orders_checked": len(orders),
                "orders_auto_delivered": delivered_count,
                "delivered_order_ids": delivered_order_ids,
                "trigger": "scheduled",
            },
        )

        await db.commit()

        logger.info(
            "AfterShip batch sync complete: %d checked, %d auto-delivered (1 API call)",
            len(orders), delivered_count,
        )
        return {"checked": len(orders), "delivered": delivered_count, "api_calls": 1}


