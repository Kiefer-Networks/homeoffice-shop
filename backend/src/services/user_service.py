import logging
from datetime import date
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import BadRequestError, NotFoundError
from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.hibob_purchase_review import HiBobPurchaseReview
from src.models.orm.user import User
from src.models.orm.user_budget_override import UserBudgetOverride
from src.repositories import user_repo
from src.services import budget_service, order_service
from src.services.auth_service import logout as revoke_user_sessions

logger = logging.getLogger(__name__)

_ALLOWED_AVATAR_HOSTS = {
    "images.hibob.com",
    "lh3.googleusercontent.com",
    "www.gravatar.com",
}


async def get_departments(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(User.department)
        .where(User.department.isnot(None), User.is_active.is_(True))
        .group_by(User.department)
        .order_by(User.department)
    )
    return [row[0] for row in result.all()]


async def get_user_detail(db: AsyncSession, user_id: UUID) -> dict:
    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    orders, _ = await order_service.get_orders(db, user_id=user_id, page=1, per_page=100)

    result = await db.execute(
        select(BudgetAdjustment)
        .where(
            BudgetAdjustment.user_id == user_id,
            BudgetAdjustment.source != "hibob",
        )
        .order_by(BudgetAdjustment.created_at.desc())
    )
    adjustments = [
        {
            "id": a.id,
            "user_id": a.user_id,
            "amount_cents": a.amount_cents,
            "reason": a.reason,
            "created_by": a.created_by,
            "created_at": a.created_at,
        }
        for a in result.scalars().all()
    ]

    spent = await budget_service.get_live_spent_cents(db, user_id)
    adjustment_total = await budget_service.get_live_adjustment_cents(db, user_id)
    available = await budget_service.get_live_available_cents(db, user_id, target.total_budget_cents)

    rules = await budget_service.get_budget_rules(db)
    overrides = await budget_service.get_user_overrides(db, user_id)
    timeline = []
    if target.start_date:
        timeline = budget_service.get_budget_timeline(target.start_date, rules, overrides)

    override_dicts = [
        {
            "id": o.id,
            "user_id": o.user_id,
            "effective_from": o.effective_from,
            "effective_until": o.effective_until,
            "initial_cents": o.initial_cents,
            "yearly_increment_cents": o.yearly_increment_cents,
            "reason": o.reason,
            "created_by": o.created_by,
            "created_at": o.created_at,
        }
        for o in overrides
    ]

    pr_result = await db.execute(
        select(HiBobPurchaseReview)
        .where(HiBobPurchaseReview.user_id == user_id)
        .order_by(HiBobPurchaseReview.entry_date.desc())
    )
    purchase_reviews = [
        {
            "id": pr.id,
            "entry_date": pr.entry_date,
            "description": pr.description,
            "amount_cents": pr.amount_cents,
            "currency": pr.currency,
            "status": pr.status,
            "matched_order_id": pr.matched_order_id,
        }
        for pr in pr_result.scalars().all()
    ]

    return {
        "user": target,
        "orders": orders,
        "adjustments": adjustments,
        "budget_summary": {
            "total_budget_cents": target.total_budget_cents,
            "spent_cents": spent,
            "adjustment_cents": adjustment_total,
            "available_cents": available,
        },
        "budget_timeline": timeline,
        "budget_overrides": override_dicts,
        "purchase_reviews": purchase_reviews,
    }


async def change_role(
    db: AsyncSession, user_id: UUID, new_role: str, admin_id: UUID,
) -> tuple[User, str]:
    if user_id == admin_id:
        raise BadRequestError("Cannot change your own role")

    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    old_role = target.role
    target.role = new_role
    await db.flush()
    await revoke_user_sessions(db, user_id)
    return target, old_role


async def set_probation_override(
    db: AsyncSession, user_id: UUID, override: bool,
) -> User:
    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    target.probation_override = override
    await db.flush()
    return target


async def create_budget_override(
    db: AsyncSession,
    user_id: UUID,
    *,
    effective_from: date,
    effective_until: date | None = None,
    initial_cents: int,
    yearly_increment_cents: int,
    reason: str,
    created_by: UUID,
) -> UserBudgetOverride:
    target = await user_repo.get_by_id(db, user_id)
    if not target:
        raise NotFoundError("User not found")

    override = UserBudgetOverride(
        user_id=user_id,
        effective_from=effective_from,
        effective_until=effective_until,
        initial_cents=initial_cents,
        yearly_increment_cents=yearly_increment_cents,
        reason=reason,
        created_by=created_by,
    )
    db.add(override)
    await db.flush()
    return override


async def update_budget_override(
    db: AsyncSession, user_id: UUID, override_id: UUID, data: dict,
) -> UserBudgetOverride:
    override = await db.get(UserBudgetOverride, override_id)
    if not override or override.user_id != user_id:
        raise NotFoundError("Budget override not found")

    for field in ("effective_from", "effective_until", "initial_cents", "yearly_increment_cents", "reason"):
        if field in data:
            setattr(override, field, data[field])
    await db.flush()
    return override


async def delete_budget_override(
    db: AsyncSession, user_id: UUID, override_id: UUID,
) -> None:
    override = await db.get(UserBudgetOverride, override_id)
    if not override or override.user_id != user_id:
        raise NotFoundError("Budget override not found")
    await db.delete(override)
    await db.flush()


# ── Functions extracted from routes ──────────────────────────────────────────


async def list_users(
    db: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 50,
    q: str | None = None,
    department: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    sort: str = "name_asc",
) -> dict:
    """List users with pagination and filtering. Wraps user_repo.get_all()."""
    users, total = await user_repo.get_all(
        db, page=page, per_page=per_page, q=q,
        department=department, role=role, is_active=is_active, sort=sort,
    )
    return {"items": users, "total": total, "page": page, "per_page": per_page}


async def search_users(
    db: AsyncSession, q: str, limit: int = 20,
) -> list[User]:
    """Search active users by name or email. Wraps user_repo.search_active()."""
    return await user_repo.search_active(db, q, limit)


async def get_avatar_url(db: AsyncSession, user_id: UUID) -> str:
    """Look up a user's avatar URL and validate it against the allow-list.

    Returns the validated avatar URL string.
    Raises NotFoundError if the user or avatar is missing.
    Raises BadRequestError if the URL is not from an allowed host.
    """
    target_user = await user_repo.get_by_id(db, user_id)
    if not target_user or not target_user.avatar_url:
        raise NotFoundError("Avatar not found")

    parsed = urlparse(target_user.avatar_url)
    if parsed.scheme not in ("https",) or parsed.hostname not in _ALLOWED_AVATAR_HOSTS:
        raise BadRequestError("Invalid avatar URL")

    return target_user.avatar_url
