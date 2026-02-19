from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.core.exceptions import BadRequestError, NotFoundError
from src.core.search import ilike_escape
from src.mappers.purchase_review import review_to_dict as _review_to_dict
from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.hibob_purchase_review import HiBobPurchaseReview
from src.models.orm.order import Order
from src.models.orm.user import User
from src.services.budget_service import refresh_budget_cache


async def list_reviews(
    db: AsyncSession,
    *,
    status: str | None = None,
    user_id: UUID | None = None,
    q: str | None = None,
    sort: str = "date_desc",
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    UserTarget = aliased(User, name="user_target")

    conditions = []
    if status:
        conditions.append(HiBobPurchaseReview.status == status)
    if user_id:
        conditions.append(HiBobPurchaseReview.user_id == user_id)
    if q:
        search = ilike_escape(q)
        conditions.append(
            (UserTarget.display_name.ilike(search))
            | (HiBobPurchaseReview.description.ilike(search))
        )

    base = (
        select(HiBobPurchaseReview, UserTarget.display_name)
        .join(UserTarget, HiBobPurchaseReview.user_id == UserTarget.id, isouter=True)
    )
    if conditions:
        base = base.where(and_(*conditions))

    count_q = (
        select(func.count())
        .select_from(HiBobPurchaseReview)
        .join(UserTarget, HiBobPurchaseReview.user_id == UserTarget.id, isouter=True)
    )
    if conditions:
        count_q = count_q.where(and_(*conditions))

    count_result = await db.execute(count_q)
    total = count_result.scalar() or 0

    sort_map = {
        "date_desc": HiBobPurchaseReview.entry_date.desc(),
        "date_asc": HiBobPurchaseReview.entry_date.asc(),
        "amount_desc": HiBobPurchaseReview.amount_cents.desc(),
        "amount_asc": HiBobPurchaseReview.amount_cents.asc(),
        "employee_asc": UserTarget.display_name.asc(),
        "employee_desc": UserTarget.display_name.desc(),
    }
    order_clause = sort_map.get(sort, HiBobPurchaseReview.entry_date.desc())

    result = await db.execute(
        base.order_by(order_clause)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = result.all()
    items = []
    for review, user_name in rows:
        items.append({**_review_to_dict(review), "user_display_name": user_name})
    return items, total


async def get_pending_count(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(HiBobPurchaseReview).where(
            HiBobPurchaseReview.status == "pending"
        )
    )
    return result.scalar() or 0


async def _reload_with_user(db: AsyncSession, review_id: UUID) -> dict:
    UserTarget = aliased(User, name="user_target")
    result = await db.execute(
        select(HiBobPurchaseReview, UserTarget.display_name)
        .join(UserTarget, HiBobPurchaseReview.user_id == UserTarget.id, isouter=True)
        .where(HiBobPurchaseReview.id == review_id)
    )
    row = result.one()
    r, user_name = row
    return {**_review_to_dict(r), "user_display_name": user_name}


async def match_review(
    db: AsyncSession,
    review_id: UUID,
    order_id: UUID,
    staff_id: UUID,
) -> dict:
    review = await db.get(HiBobPurchaseReview, review_id)
    if not review:
        raise NotFoundError("Review not found")
    if review.status != "pending":
        raise BadRequestError("Only pending reviews can be matched")

    order = await db.get(Order, order_id)
    if not order:
        raise NotFoundError("Order not found")

    review.status = "matched"
    review.matched_order_id = order_id
    review.resolved_by = staff_id
    review.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    return await _reload_with_user(db, review_id)


async def adjust_review(
    db: AsyncSession,
    review_id: UUID,
    staff_id: UUID,
) -> dict:
    review = await db.get(HiBobPurchaseReview, review_id)
    if not review:
        raise NotFoundError("Review not found")
    if review.status != "pending":
        raise BadRequestError("Only pending reviews can be adjusted")

    adjustment = BudgetAdjustment(
        user_id=review.user_id,
        amount_cents=-review.amount_cents,
        reason=f"HiBob purchase: {review.description}",
        created_by=staff_id,
        source="hibob",
        hibob_entry_id=review.hibob_entry_id,
    )
    db.add(adjustment)
    await db.flush()

    review.status = "adjusted"
    review.adjustment_id = adjustment.id
    review.resolved_by = staff_id
    review.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    await refresh_budget_cache(db, review.user_id)
    return await _reload_with_user(db, review_id)


async def dismiss_review(
    db: AsyncSession,
    review_id: UUID,
    staff_id: UUID,
) -> dict:
    review = await db.get(HiBobPurchaseReview, review_id)
    if not review:
        raise NotFoundError("Review not found")
    if review.status != "pending":
        raise BadRequestError("Only pending reviews can be dismissed")

    review.status = "dismissed"
    review.resolved_by = staff_id
    review.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    return await _reload_with_user(db, review_id)
