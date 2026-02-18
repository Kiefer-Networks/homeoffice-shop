import logging
from datetime import date
from uuid import UUID

from sqlalchemy import select, func, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.core.exceptions import BadRequestError, NotFoundError
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


# ── Budget Rule CRUD ─────────────────────────────────────────────────────────

async def create_budget_rule(
    db: AsyncSession,
    *,
    effective_from: date,
    initial_cents: int,
    yearly_increment_cents: int,
    created_by: UUID,
) -> BudgetRule:
    rule = BudgetRule(
        effective_from=effective_from,
        initial_cents=initial_cents,
        yearly_increment_cents=yearly_increment_cents,
        created_by=created_by,
    )
    db.add(rule)
    await db.flush()
    return rule


async def update_budget_rule(
    db: AsyncSession,
    rule_id: UUID,
    data: dict,
) -> BudgetRule:
    rule = await db.get(BudgetRule, rule_id)
    if not rule:
        raise NotFoundError("Budget rule not found")
    if data.get("effective_from") is not None:
        rule.effective_from = data["effective_from"]
    if data.get("initial_cents") is not None:
        rule.initial_cents = data["initial_cents"]
    if data.get("yearly_increment_cents") is not None:
        rule.yearly_increment_cents = data["yearly_increment_cents"]
    await db.flush()
    return rule


async def delete_budget_rule(db: AsyncSession, rule_id: UUID) -> None:
    rule = await db.get(BudgetRule, rule_id)
    if not rule:
        raise NotFoundError("Budget rule not found")
    count_result = await db.execute(select(BudgetRule.id))
    if len(count_result.all()) <= 1:
        raise BadRequestError("Cannot delete the last budget rule")
    await db.delete(rule)
    await db.flush()


# ── Budget Adjustment CRUD ───────────────────────────────────────────────────

async def list_adjustments(
    db: AsyncSession,
    *,
    user_id: UUID | None = None,
    q: str | None = None,
    sort: str = "newest",
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    UserTarget = aliased(User, name="user_target")
    UserCreator = aliased(User, name="user_creator")

    conditions = []
    if user_id:
        conditions.append(BudgetAdjustment.user_id == user_id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search = f"%{escaped}%"
        conditions.append(
            or_(
                UserTarget.display_name.ilike(search),
                BudgetAdjustment.reason.ilike(search),
            )
        )
    where = and_(*conditions) if conditions else True

    base_query = (
        select(BudgetAdjustment, UserTarget.display_name, UserCreator.display_name)
        .join(UserTarget, BudgetAdjustment.user_id == UserTarget.id, isouter=True)
        .join(UserCreator, BudgetAdjustment.created_by == UserCreator.id, isouter=True)
        .where(where)
    )

    count_result = await db.execute(
        select(func.count())
        .select_from(BudgetAdjustment)
        .join(UserTarget, BudgetAdjustment.user_id == UserTarget.id, isouter=True)
        .where(where)
    )
    total = count_result.scalar() or 0

    order_clause = {
        "newest": BudgetAdjustment.created_at.desc(),
        "oldest": BudgetAdjustment.created_at.asc(),
        "amount_asc": BudgetAdjustment.amount_cents.asc(),
        "amount_desc": BudgetAdjustment.amount_cents.desc(),
    }.get(sort, BudgetAdjustment.created_at.desc())

    result = await db.execute(
        base_query.order_by(order_clause)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = result.all()
    items = []
    for adj, user_name, creator_name in rows:
        items.append({
            "id": adj.id,
            "user_id": adj.user_id,
            "amount_cents": adj.amount_cents,
            "reason": adj.reason,
            "source": adj.source,
            "hibob_entry_id": adj.hibob_entry_id,
            "created_by": adj.created_by,
            "created_at": adj.created_at,
            "user_display_name": user_name,
            "creator_display_name": creator_name,
        })
    return items, total


async def create_adjustment(
    db: AsyncSession,
    *,
    user_id: UUID,
    amount_cents: int,
    reason: str,
    created_by: UUID,
) -> BudgetAdjustment:
    target = await db.get(User, user_id)
    if not target:
        raise NotFoundError("User not found")

    adjustment = BudgetAdjustment(
        user_id=user_id,
        amount_cents=amount_cents,
        reason=reason,
        created_by=created_by,
    )
    db.add(adjustment)
    await db.flush()
    await refresh_budget_cache(db, user_id)
    return adjustment


async def update_adjustment(
    db: AsyncSession,
    adjustment_id: UUID,
    *,
    amount_cents: int,
    reason: str,
) -> tuple[BudgetAdjustment, dict]:
    adjustment = await db.get(BudgetAdjustment, adjustment_id)
    if not adjustment:
        raise NotFoundError("Adjustment not found")
    if adjustment.source == "hibob":
        raise BadRequestError(
            "Cannot modify HiBob-synced adjustments. Manage via Purchase Reviews."
        )

    old = {"amount_cents": adjustment.amount_cents, "reason": adjustment.reason}
    adjustment.amount_cents = amount_cents
    adjustment.reason = reason
    await db.flush()
    await refresh_budget_cache(db, adjustment.user_id)

    # Re-query with user joins
    UserTarget = aliased(User, name="user_target")
    UserCreator = aliased(User, name="user_creator")
    result = await db.execute(
        select(BudgetAdjustment, UserTarget.display_name, UserCreator.display_name)
        .join(UserTarget, BudgetAdjustment.user_id == UserTarget.id, isouter=True)
        .join(UserCreator, BudgetAdjustment.created_by == UserCreator.id, isouter=True)
        .where(BudgetAdjustment.id == adjustment_id)
    )
    row = result.one()
    adj, user_name, creator_name = row
    enriched = {
        "id": adj.id,
        "user_id": adj.user_id,
        "amount_cents": adj.amount_cents,
        "reason": adj.reason,
        "created_by": adj.created_by,
        "created_at": adj.created_at,
        "user_display_name": user_name,
        "creator_display_name": creator_name,
    }
    return adjustment, {**old, "new_amount_cents": amount_cents, "new_reason": reason}, enriched


async def delete_adjustment(
    db: AsyncSession, adjustment_id: UUID,
) -> tuple[UUID, dict]:
    adjustment = await db.get(BudgetAdjustment, adjustment_id)
    if not adjustment:
        raise NotFoundError("Adjustment not found")
    if adjustment.source == "hibob":
        raise BadRequestError(
            "Cannot modify HiBob-synced adjustments. Manage via Purchase Reviews."
        )

    user_id = adjustment.user_id
    details = {
        "target_user_id": str(user_id),
        "amount_cents": adjustment.amount_cents,
        "reason": adjustment.reason,
    }
    await db.delete(adjustment)
    await db.flush()
    await refresh_budget_cache(db, user_id)
    return user_id, details
