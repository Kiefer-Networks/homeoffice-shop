import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.order import Order, OrderItem
from src.models.orm.product import Product
from src.models.orm.user import User
from src.notifications.service import notify_user_email

logger = logging.getLogger(__name__)


async def send_delivery_reminders(db: AsyncSession) -> int:
    """Check for 'ordered' orders past expected_delivery + 1 day.

    Sends an email to the employee's manager (or to staff if no manager).
    Marks the order so the reminder is only sent once by setting
    admin_note with a reminder tag.

    Returns the number of reminders sent.
    """
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Find orders that are still 'ordered', have an expected_delivery date
    # that has passed (+ 1 day buffer), and haven't been reminded yet.
    result = await db.execute(
        select(Order).where(
            Order.status == "ordered",
            Order.expected_delivery.isnot(None),
            Order.expected_delivery <= yesterday,
            Order.delivery_reminder_sent.is_(False),
        )
    )
    orders = list(result.scalars().all())

    if not orders:
        return 0

    sent = 0
    for order in orders:
        try:
            user = await db.get(User, order.user_id)
            if not user:
                continue

            # Load items with product names
            items_result = await db.execute(
                select(OrderItem, Product.name)
                .join(Product, OrderItem.product_id == Product.id, isouter=True)
                .where(OrderItem.order_id == order.id)
            )
            items = [
                {
                    "product_name": product_name or "Product",
                    "quantity": item.quantity,
                    "price_cents": item.price_cents * item.quantity,
                }
                for item, product_name in items_result.all()
            ]

            # Determine recipient: manager_email if available, otherwise skip
            recipient = user.manager_email
            if not recipient:
                logger.info(
                    "No manager email for user %s (order %s), skipping reminder",
                    user.id, order.id,
                )
                # Still mark as sent to avoid retrying every day
                order.delivery_reminder_sent = True
                await db.flush()
                continue

            # Mark before sending to prevent infinite daily retries on SMTP failure
            order.delivery_reminder_sent = True
            await db.flush()

            success = await notify_user_email(
                to=recipient,
                subject=f"Delivery confirmation needed: Order #{str(order.id)[:8]}",
                template_name="delivery_reminder.html",
                context={
                    "order_id_short": str(order.id)[:8],
                    "user_name": user.display_name or user.email,
                    "expected_delivery": order.expected_delivery,
                    "items": items,
                    "total_cents": order.total_cents,
                },
            )

            if success:
                sent += 1
                logger.info(
                    "Delivery reminder sent for order %s to manager %s",
                    order.id, recipient,
                )
            else:
                logger.warning(
                    "Delivery reminder email failed for order %s to %s",
                    order.id, recipient,
                )
        except Exception:
            logger.exception("Failed to process delivery reminder for order %s", order.id)

    return sent
