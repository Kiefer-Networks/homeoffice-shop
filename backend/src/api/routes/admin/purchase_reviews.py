from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.models.dto.hibob import (
    HiBobPurchaseReviewListResponse,
    HiBobPurchaseReviewMatchRequest,
    HiBobPurchaseReviewResponse,
)
from src.models.orm.user import User
from src.services import purchase_review_service

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
    items, total = await purchase_review_service.list_reviews(
        db, status=status, user_id=user_id, q=q, sort=sort, page=page, per_page=per_page,
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/pending-count")
async def get_pending_count(
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    count = await purchase_review_service.get_pending_count(db)
    return {"count": count}


@router.put("/{review_id}/match", response_model=HiBobPurchaseReviewResponse)
async def match_review(
    review_id: UUID,
    body: HiBobPurchaseReviewMatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    result = await purchase_review_service.match_review(
        db, review_id, body.order_id, staff.id,
    )

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.purchase_review.matched",
        resource_type="hibob_purchase_review", resource_id=review_id,
        details={
            "order_id": str(body.order_id),
            "hibob_entry_id": result.get("hibob_entry_id"),
        },
        ip_address=ip,
    )
    return result


@router.put("/{review_id}/adjust", response_model=HiBobPurchaseReviewResponse)
async def adjust_review(
    review_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    result = await purchase_review_service.adjust_review(db, review_id, staff.id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.purchase_review.adjusted",
        resource_type="hibob_purchase_review", resource_id=review_id,
        details={
            "adjustment_id": str(result.get("adjustment_id")),
            "amount_cents": -(result.get("amount_cents", 0)),
            "hibob_entry_id": result.get("hibob_entry_id"),
        },
        ip_address=ip,
    )
    return result


@router.put("/{review_id}/dismiss", response_model=HiBobPurchaseReviewResponse)
async def dismiss_review(
    review_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    result = await purchase_review_service.dismiss_review(db, review_id, staff.id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.purchase_review.dismissed",
        resource_type="hibob_purchase_review", resource_id=review_id,
        details={"hibob_entry_id": result.get("hibob_entry_id")},
        ip_address=ip,
    )
    return result
