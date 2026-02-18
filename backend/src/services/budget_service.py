import logging
from datetime import date
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.budget_rule import BudgetRule
from src.models.orm.order import Order
from src.models.orm.user import User
from src.models.orm.user_budget_override import UserBudgetOverride
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


async def get_budget_rules(db: AsyncSession) -> list[BudgetRule]:
    result = await db.execute(
        select(BudgetRule).order_by(BudgetRule.effective_from)
    )
    return list(result.scalars().all())


async def get_user_overrides(db: AsyncSession, user_id: UUID) -> list[UserBudgetOverride]:
    result = await db.execute(
        select(UserBudgetOverride)
        .where(UserBudgetOverride.user_id == user_id)
        .order_by(UserBudgetOverride.effective_from)
    )
    return list(result.scalars().all())


def get_budget_timeline(
    start_date: date,
    rules: list[BudgetRule],
    overrides: list[UserBudgetOverride],
) -> list[dict]:
    """Build year-by-year budget timeline using rules and per-user overrides."""
    if not start_date:
        return []

    from dateutil.relativedelta import relativedelta

    today = date.today()
    if start_date > today:
        return []

    timeline = []
    cumulative = 0
    current = start_date

    while current <= today:
        year_end = current + relativedelta(years=1) - relativedelta(days=1)
        year_num = current.year

        # Check for user override first
        override = None
        for o in overrides:
            if o.effective_from <= current and (o.effective_until is None or o.effective_until >= current):
                override = o
                break

        if override:
            amount = override.initial_cents if current == start_date else override.yearly_increment_cents
            source = "override"
        else:
            # Find applicable global rule (latest rule with effective_from <= current)
            applicable_rule = None
            for r in rules:
                if r.effective_from <= current:
                    applicable_rule = r
                else:
                    break
            if applicable_rule:
                amount = applicable_rule.initial_cents if current == start_date else applicable_rule.yearly_increment_cents
                source = "global"
            else:
                # Fallback to settings
                amount = get_setting_int("budget_initial_cents") if current == start_date else get_setting_int("budget_yearly_increment_cents")
                source = "global"

        cumulative += amount
        timeline.append({
            "year": year_num,
            "period_from": current.isoformat(),
            "period_to": min(year_end, today).isoformat(),
            "amount_cents": amount,
            "cumulative_cents": cumulative,
            "source": source,
        })

        current = current + relativedelta(years=1)

    return timeline


async def calculate_total_budget_from_rules(
    db: AsyncSession, start_date: date | None, user_id: UUID | None = None
) -> int:
    """Calculate total budget using rules/overrides when available."""
    if start_date is None or start_date > date.today():
        return 0

    rules = await get_budget_rules(db)
    overrides = []
    if user_id:
        overrides = await get_user_overrides(db, user_id)

    if not rules and not overrides:
        return calculate_total_budget_cents(start_date)

    timeline = get_budget_timeline(start_date, rules, overrides)
    if not timeline:
        return 0
    return timeline[-1]["cumulative_cents"]


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
