import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit.service import write_audit_log
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

    # Batch-load all users referenced by orders
    user_ids = list({order.user_id for order in orders})
    users_result = await db.execute(
        select(User).where(User.id.in_(user_ids))
    )
    users_map = {u.id: u for u in users_result.scalars().all()}

    # Batch-load all order items with product names
    order_ids = [order.id for order in orders]
    items_result = await db.execute(
        select(OrderItem, Product.name)
        .join(Product, OrderItem.product_id == Product.id, isouter=True)
        .where(OrderItem.order_id.in_(order_ids))
    )
    all_items_rows = items_result.all()

    # Group items by order_id
    items_by_order: dict = {}
    for item, product_name in all_items_rows:
        items_by_order.setdefault(item.order_id, []).append({
            "product_name": product_name or "Product",
            "quantity": item.quantity,
            "price_cents": item.price_cents * item.quantity,
        })

    sent = 0
    for order in orders:
        try:
            user = users_map.get(order.user_id)
            if not user:
                continue

            items = items_by_order.get(order.id, [])

            # Determine recipient: manager_email if available, otherwise skip manager notification
            recipient = user.manager_email
            if not recipient:
                logger.info(
                    "No manager email for user %s (order %s), skipping manager reminder",
                    user.id, order.id,
                )
                # Still mark as sent to avoid retrying every day
                order.delivery_reminder_sent = True
                await db.flush()
                await write_audit_log(
                    db,
                    user_id=order.user_id,
                    action="delivery_reminder.skipped",
                    resource_type="order",
                    resource_id=order.id,
                    details={
                        "reason": "no_manager_email",
                        "expected_delivery": order.expected_delivery,
                        "order_total_cents": order.total_cents,
                    },
                )
                # Still notify the employee about the delay
                try:
                    await notify_user_email(
                        to=user.email,
                        subject="Delivery Update \u2014 Your order may be delayed",
                        template_name="delivery_delayed_employee.html",
                        context={
                            "order_id_short": str(order.id)[:8],
                            "expected_delivery": order.expected_delivery,
                            "items": items,
                            "total_cents": order.total_cents,
                        },
                    )
                except Exception:
                    logger.exception(
                        "Failed to send delivery delay notification to employee %s for order %s",
                        user.id, order.id,
                    )
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
                await write_audit_log(
                    db,
                    user_id=order.user_id,
                    action="delivery_reminder.sent",
                    resource_type="order",
                    resource_id=order.id,
                    details={
                        "recipient": recipient,
                        "employee_name": user.display_name or user.email,
                        "expected_delivery": order.expected_delivery,
                        "order_total_cents": order.total_cents,
                        "items_count": len(items),
                    },
                )
            else:
                logger.warning(
                    "Delivery reminder email failed for order %s to %s",
                    order.id, recipient,
                )
                await write_audit_log(
                    db,
                    user_id=order.user_id,
                    action="delivery_reminder.failed",
                    resource_type="order",
                    resource_id=order.id,
                    details={
                        "recipient": recipient,
                        "expected_delivery": order.expected_delivery,
                        "reason": "email_send_failed",
                    },
                )

            # Also notify the employee about the delay
            try:
                employee_success = await notify_user_email(
                    to=user.email,
                    subject="Delivery Update \u2014 Your order may be delayed",
                    template_name="delivery_delayed_employee.html",
                    context={
                        "order_id_short": str(order.id)[:8],
                        "expected_delivery": order.expected_delivery,
                        "items": items,
                        "total_cents": order.total_cents,
                    },
                )
                if employee_success:
                    logger.info(
                        "Delivery delay notification sent to employee %s for order %s",
                        user.id, order.id,
                    )
                else:
                    logger.warning(
                        "Delivery delay notification to employee %s failed for order %s",
                        user.id, order.id,
                    )
            except Exception:
                logger.exception(
                    "Failed to send delivery delay notification to employee %s for order %s",
                    user.id, order.id,
                )
        except Exception:
            logger.exception("Failed to process delivery reminder for order %s", order.id)

    return sent
