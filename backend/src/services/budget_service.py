import logging
from datetime import date
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.order import Order
from src.models.orm.user import User
from src.services.settings_service import get_cached_settings, get_setting_int

logger = logging.getLogger(__name__)


def calculate_total_budget_cents(
    start_date: date | None, app_settings: dict[str, str] | None = None
) -> int:
    if start_date is None or start_date > date.today():
        return 0

    if app_settings:
        initial = int(app_settings.get("budget_initial_cents", "75000"))
        increment = int(app_settings.get("budget_yearly_increment_cents", "25000"))
    else:
        initial = get_setting_int("budget_initial_cents")
        increment = get_setting_int("budget_yearly_increment_cents")

    from dateutil.relativedelta import relativedelta

    completed_years = relativedelta(date.today(), start_date).years
    return initial + (completed_years * increment)


async def get_available_budget_cents(db: AsyncSession, user_id: UUID) -> int:
    user = await db.get(User, user_id)
    if not user:
        return 0
    return user.total_budget_cents + user.cached_adjustment_cents - user.cached_spent_cents


async def get_live_spent_cents(db: AsyncSession, user_id: UUID) -> int:
    """Calculate actual spent from orders (pending + ordered + delivered)."""
    result = await db.execute(
        select(func.coalesce(func.sum(Order.total_cents), 0)).where(
            Order.user_id == user_id,
            Order.status.in_(["pending", "ordered", "delivered"]),
        )
    )
    return result.scalar() or 0


async def get_live_adjustment_cents(db: AsyncSession, user_id: UUID) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(BudgetAdjustment.amount_cents), 0)).where(
            BudgetAdjustment.user_id == user_id
        )
    )
    return result.scalar() or 0


async def refresh_budget_cache(db: AsyncSession, user_id: UUID) -> None:
    """Recalculate and store cached budget values."""
    from datetime import datetime, timezone

    spent = await get_live_spent_cents(db, user_id)
    adjustments = await get_live_adjustment_cents(db, user_id)

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            cached_spent_cents=spent,
            cached_adjustment_cents=adjustments,
            budget_cache_updated_at=datetime.now(timezone.utc),
        )
    )


async def check_budget_for_order(
    db: AsyncSession, user_id: UUID, order_total_cents: int
) -> bool:
    """Check if user has sufficient budget using live calculation with row lock."""
    result = await db.execute(
        select(User).where(User.id == user_id).with_for_update()
    )
    user = result.scalar_one_or_none()
    if not user:
        return False

    spent = await get_live_spent_cents(db, user_id)
    adjustments = await get_live_adjustment_cents(db, user_id)
    available = user.total_budget_cents + adjustments - spent

    return order_total_cents <= available
