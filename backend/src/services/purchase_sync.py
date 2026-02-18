import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.hibob.client import HiBobClientProtocol
from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.hibob_purchase_review import HiBobPurchaseReview
from src.models.orm.hibob_purchase_sync_log import HiBobPurchaseSyncLog
from src.models.orm.order import Order
from src.models.orm.user import User
from src.services.budget_service import refresh_budget_cache
from src.services.settings_service import get_setting, load_settings

logger = logging.getLogger(__name__)

AMOUNT_TOLERANCE_CENTS = 100
DATE_TOLERANCE_DAYS = 7


def _parse_amount_cents(raw_value: str) -> int:
    """Parse amount string to cents. Handles '750.00', '750,00', '1.234,56'."""
    s = str(raw_value).strip()

    # Remove currency symbols and whitespace
    s = re.sub(r"[€$£\s]", "", s)

    if not s:
        raise ValueError(f"Empty amount: {raw_value!r}")

    # Detect European format: "1.234,56" or "750,00"
    # If comma exists and is after the last dot, treat comma as decimal
    has_comma = "," in s
    has_dot = "." in s

    if has_comma and has_dot:
        # "1.234,56" -> European: dots are thousands, comma is decimal
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            # "1,234.56" -> US format: commas are thousands
            s = s.replace(",", "")
    elif has_comma:
        # "750,00" -> comma is decimal
        s = s.replace(",", ".")
    # else: "750.00" or "750" -> already correct

    return round(float(s) * 100)


def _find_matching_orders(
    orders: list[Order], amount_cents: int, entry_date: date
) -> list[Order]:
    """Find orders within tolerance for amount and date."""
    matches = []
    for order in orders:
        if order.status not in ("pending", "ordered", "delivered"):
            continue
        amount_diff = abs(order.total_cents - amount_cents)
        date_diff = abs((order.created_at.date() - entry_date).days)
        if amount_diff <= AMOUNT_TOLERANCE_CENTS and date_diff <= DATE_TOLERANCE_DAYS:
            matches.append(order)
    return matches


async def sync_purchases(
    db: AsyncSession,
    client: HiBobClientProtocol,
    triggered_by: UUID | None = None,
) -> HiBobPurchaseSyncLog:
    """Sync HiBob custom table purchases into the shop budget system."""
    log = HiBobPurchaseSyncLog(status="running", triggered_by=triggered_by)
    db.add(log)
    await db.flush()

    try:
        # Reload settings from DB to handle multi-worker cache
        await load_settings(db)
        table_id = get_setting("hibob_purchase_table_id")
        if not table_id:
            raise ValueError("HiBob purchase table not configured")

        col_date = get_setting("hibob_purchase_col_date")
        col_description = get_setting("hibob_purchase_col_description")
        col_amount = get_setting("hibob_purchase_col_amount")
        col_currency = get_setting("hibob_purchase_col_currency")

        # Fetch all active users with hibob_id
        result = await db.execute(
            select(User).where(
                User.is_active.is_(True),
                User.hibob_id.isnot(None),
            )
        )
        users = list(result.scalars().all())
        logger.info("Purchase sync: processing %d users", len(users))

        entries_found = 0
        matched_count = 0
        auto_adjusted_count = 0
        pending_count = 0
        affected_user_ids: set[UUID] = set()

        # Fetch custom tables sequentially with delay to avoid HiBob rate limits
        user_rows: dict[UUID, list[dict]] = {}
        for i, user in enumerate(users):
            try:
                rows = await client.get_custom_table(user.hibob_id, table_id)
                if rows:
                    user_rows[user.id] = rows
            except Exception:
                logger.warning(
                    "Failed to fetch custom table for user %s (hibob_id=%s)",
                    user.id, user.hibob_id,
                )
            # Small delay between requests to stay within rate limits
            if i < len(users) - 1:
                await asyncio.sleep(0.3)

        logger.info("Purchase sync: fetched custom tables, %d users have entries", len(user_rows))

        for user in users:
            rows = user_rows.get(user.id)
            if not rows:
                continue

            # Pre-fetch user's orders for matching
            order_result = await db.execute(
                select(Order).where(
                    Order.user_id == user.id,
                    Order.status.in_(["pending", "ordered", "delivered"]),
                )
            )
            user_orders = list(order_result.scalars().all())

            for row in rows:
                entry_id = str(row.get("id", ""))
                if not entry_id:
                    continue

                # Check idempotency: skip if already processed
                existing = await db.execute(
                    select(HiBobPurchaseReview.id).where(
                        HiBobPurchaseReview.hibob_entry_id == entry_id
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    continue

                entries_found += 1

                # Extract fields
                try:
                    raw_date = row.get(col_date, "")
                    if isinstance(raw_date, str) and raw_date:
                        entry_date = date.fromisoformat(raw_date)
                    elif isinstance(raw_date, date):
                        entry_date = raw_date
                    else:
                        logger.warning("Skipping entry %s: no date", entry_id)
                        continue

                    description = str(row.get(col_description, ""))

                    # Handle HiBob compound amount fields: {"value": 270, "currency": "EUR"}
                    raw_amount_field = row.get(col_amount, "0")
                    if isinstance(raw_amount_field, dict):
                        raw_amount = str(raw_amount_field.get("value", "0"))
                        currency = str(raw_amount_field.get("currency", "EUR")) or "EUR"
                    else:
                        raw_amount = str(raw_amount_field)
                        currency = str(row.get(col_currency, "EUR")) or "EUR"
                    amount_cents = _parse_amount_cents(raw_amount)
                except Exception:
                    logger.exception("Failed to parse entry %s", entry_id)
                    continue

                # Try auto-match
                matching_orders = _find_matching_orders(
                    user_orders, amount_cents, entry_date
                )

                review = HiBobPurchaseReview(
                    user_id=user.id,
                    hibob_employee_id=user.hibob_id,
                    hibob_entry_id=entry_id,
                    entry_date=entry_date,
                    description=description,
                    amount_cents=amount_cents,
                    currency=currency,
                    sync_log_id=log.id,
                    raw_data=row,
                )

                if len(matching_orders) == 1:
                    # Auto-match
                    review.status = "matched"
                    review.matched_order_id = matching_orders[0].id
                    matched_count += 1
                elif len(matching_orders) == 0:
                    # No match: create negative budget adjustment
                    adjustment = BudgetAdjustment(
                        user_id=user.id,
                        amount_cents=-amount_cents,
                        reason=f"HiBob purchase: {description}",
                        created_by=triggered_by or user.id,
                        source="hibob",
                        hibob_entry_id=entry_id,
                    )
                    db.add(adjustment)
                    await db.flush()
                    review.status = "adjusted"
                    review.adjustment_id = adjustment.id
                    auto_adjusted_count += 1
                    affected_user_ids.add(user.id)
                else:
                    # Ambiguous: needs review
                    review.status = "pending"
                    pending_count += 1

                db.add(review)
                await db.flush()

        # Refresh budget cache for affected users
        for uid in affected_user_ids:
            await refresh_budget_cache(db, uid)

        log.status = "completed"
        log.entries_found = entries_found
        log.matched = matched_count
        log.auto_adjusted = auto_adjusted_count
        log.pending_review = pending_count
        log.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.now(timezone.utc)
        logger.exception("Purchase sync failed")

    await db.flush()
    return log
