from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.dto.hibob import (
    HiBobPurchaseReviewListResponse,
    HiBobPurchaseReviewMatchRequest,
    HiBobPurchaseReviewResponse,
)
from src.models.orm.budget_adjustment import BudgetAdjustment
from src.models.orm.hibob_purchase_review import HiBobPurchaseReview
from src.models.orm.order import Order
from src.models.orm.user import User
from src.services.budget_service import refresh_budget_cache

router = APIRouter(prefix="/purchase-reviews", tags=["admin-purchase-reviews"])


@router.get("", response_model=HiBobPurchaseReviewListResponse)
async def list_reviews(
    status: str | None = None,
    user_id: UUID | None = None,
    q: str | None = None,
    sort: str = "date_desc",
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    UserTarget = aliased(User, name="user_target")

    conditions = []
    if status:
        conditions.append(HiBobPurchaseReview.status == status)
    if user_id:
        conditions.append(HiBobPurchaseReview.user_id == user_id)
    if q:
        escaped_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search = f"%{escaped_q}%"
        conditions.append(
            (UserTarget.display_name.ilike(search))
            | (HiBobPurchaseReview.description.ilike(search))
        )

    base = (
        select(HiBobPurchaseReview, UserTarget.display_name)
        .join(UserTarget, HiBobPurchaseReview.user_id == UserTarget.id, isouter=True)
    )
    if conditions:
        from sqlalchemy import and_
        base = base.where(and_(*conditions))

    count_q = (
        select(func.count())
        .select_from(HiBobPurchaseReview)
        .join(UserTarget, HiBobPurchaseReview.user_id == UserTarget.id, isouter=True)
    )
    if conditions:
        from sqlalchemy import and_
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
        items.append({
            "id": review.id,
            "user_id": review.user_id,
            "user_display_name": user_name,
            "hibob_employee_id": review.hibob_employee_id,
            "hibob_entry_id": review.hibob_entry_id,
            "entry_date": review.entry_date,
            "description": review.description,
            "amount_cents": review.amount_cents,
            "currency": review.currency,
            "status": review.status,
            "matched_order_id": review.matched_order_id,
            "adjustment_id": review.adjustment_id,
            "resolved_by": review.resolved_by,
            "resolved_at": review.resolved_at,
            "created_at": review.created_at,
        })
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/pending-count")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    result = await db.execute(
        select(func.count()).select_from(HiBobPurchaseReview).where(
            HiBobPurchaseReview.status == "pending"
        )
    )
    return {"count": result.scalar() or 0}


@router.put("/{review_id}/match", response_model=HiBobPurchaseReviewResponse)
async def match_review(
    review_id: UUID,
    body: HiBobPurchaseReviewMatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    review = await db.get(HiBobPurchaseReview, review_id)
    if not review:
        raise NotFoundError("Review not found")
    if review.status != "pending":
        raise BadRequestError("Only pending reviews can be matched")

    order = await db.get(Order, body.order_id)
    if not order:
        raise NotFoundError("Order not found")

    review.status = "matched"
    review.matched_order_id = body.order_id
    review.resolved_by = staff.id
    review.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.purchase_review.matched",
        resource_type="hibob_purchase_review", resource_id=review.id,
        details={
            "order_id": str(body.order_id),
            "hibob_entry_id": review.hibob_entry_id,
        },
        ip_address=ip,
    )

    UserTarget = aliased(User, name="user_target")
    result = await db.execute(
        select(HiBobPurchaseReview, UserTarget.display_name)
        .join(UserTarget, HiBobPurchaseReview.user_id == UserTarget.id, isouter=True)
        .where(HiBobPurchaseReview.id == review_id)
    )
    row = result.one()
    r, user_name = row
    return {**_review_to_dict(r), "user_display_name": user_name}


@router.put("/{review_id}/adjust", response_model=HiBobPurchaseReviewResponse)
async def adjust_review(
    review_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    review = await db.get(HiBobPurchaseReview, review_id)
    if not review:
        raise NotFoundError("Review not found")
    if review.status != "pending":
        raise BadRequestError("Only pending reviews can be adjusted")

    adjustment = BudgetAdjustment(
        user_id=review.user_id,
        amount_cents=-review.amount_cents,
        reason=f"HiBob purchase: {review.description}",
        created_by=staff.id,
        source="hibob",
        hibob_entry_id=review.hibob_entry_id,
    )
    db.add(adjustment)
    await db.flush()

    review.status = "adjusted"
    review.adjustment_id = adjustment.id
    review.resolved_by = staff.id
    review.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    await refresh_budget_cache(db, review.user_id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.purchase_review.adjusted",
        resource_type="hibob_purchase_review", resource_id=review.id,
        details={
            "adjustment_id": str(adjustment.id),
            "amount_cents": -review.amount_cents,
            "hibob_entry_id": review.hibob_entry_id,
        },
        ip_address=ip,
    )

    UserTarget = aliased(User, name="user_target")
    result = await db.execute(
        select(HiBobPurchaseReview, UserTarget.display_name)
        .join(UserTarget, HiBobPurchaseReview.user_id == UserTarget.id, isouter=True)
        .where(HiBobPurchaseReview.id == review_id)
    )
    row = result.one()
    r, user_name = row
    return {**_review_to_dict(r), "user_display_name": user_name}


@router.put("/{review_id}/dismiss", response_model=HiBobPurchaseReviewResponse)
async def dismiss_review(
    review_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    review = await db.get(HiBobPurchaseReview, review_id)
    if not review:
        raise NotFoundError("Review not found")
    if review.status != "pending":
        raise BadRequestError("Only pending reviews can be dismissed")

    review.status = "dismissed"
    review.resolved_by = staff.id
    review.resolved_at = datetime.now(timezone.utc)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.purchase_review.dismissed",
        resource_type="hibob_purchase_review", resource_id=review.id,
        details={"hibob_entry_id": review.hibob_entry_id},
        ip_address=ip,
    )

    UserTarget = aliased(User, name="user_target")
    result = await db.execute(
        select(HiBobPurchaseReview, UserTarget.display_name)
        .join(UserTarget, HiBobPurchaseReview.user_id == UserTarget.id, isouter=True)
        .where(HiBobPurchaseReview.id == review_id)
    )
    row = result.one()
    r, user_name = row
    return {**_review_to_dict(r), "user_display_name": user_name}


def _review_to_dict(review: HiBobPurchaseReview) -> dict:
    return {
        "id": review.id,
        "user_id": review.user_id,
        "hibob_employee_id": review.hibob_employee_id,
        "hibob_entry_id": review.hibob_entry_id,
        "entry_date": review.entry_date,
        "description": review.description,
        "amount_cents": review.amount_cents,
        "currency": review.currency,
        "status": review.status,
        "matched_order_id": review.matched_order_id,
        "adjustment_id": review.adjustment_id,
        "resolved_by": review.resolved_by,
        "resolved_at": review.resolved_at,
        "created_at": review.created_at,
    }
