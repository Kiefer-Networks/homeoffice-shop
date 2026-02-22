import csv
import io
import logging
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import log_admin_action
from src.core.tasks import create_background_task
from src.models.dto.budget import (
    BudgetAdjustmentCreate,
    BudgetAdjustmentListResponse,
    BudgetAdjustmentResponse,
    BudgetAdjustmentUpdate,
)
from src.models.orm.user import User
from src.notifications.email import mask_email
from src.notifications.service import notify_user_email
from src.services import budget_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budgets", tags=["admin-budgets"])


async def _send_budget_notification(
    email: str, amount_cents: int, reason: str, available_budget_cents: int,
) -> None:
    try:
        await notify_user_email(
            email,
            subject="Your Budget Has Been Adjusted",
            template_name="budget_adjusted.html",
            context={
                "amount_cents": amount_cents,
                "reason": reason,
                "available_budget_cents": available_budget_cents,
            },
        )
    except Exception:
        logger.exception("Failed to send budget adjustment email to %s", mask_email(email))


@router.get("/adjustments", response_model=BudgetAdjustmentListResponse)
async def list_adjustments(
    user_id: UUID | None = None,
    q: str | None = Query(None, max_length=200),
    sort: Literal["newest", "oldest", "amount_asc", "amount_desc"] = "newest",
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    items, total = await budget_service.list_adjustments(
        db, user_id=user_id, q=q, sort=sort, page=page, per_page=per_page,
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/adjustments/export")
async def export_adjustments_csv(
    request: Request,
    q: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    MAX_EXPORT_ROWS = 10000
    items, _ = await budget_service.list_adjustments(
        db, q=q, page=1, per_page=MAX_EXPORT_ROWS,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee", "Amount (EUR)", "Reason", "Created By", "Date"])
    for item in items:
        amount_cents = item.get("amount_cents") or 0
        amount_eur = f"{amount_cents / 100:.2f}"
        writer.writerow([
            item.get("user_display_name", ""),
            amount_eur,
            item.get("reason", ""),
            item.get("creator_display_name", ""),
            str(item.get("created_at", "")),
        ])

    await log_admin_action(
        db, request, admin.id, "admin.adjustments.exported",
        resource_type="budget_adjustment",
        details={"filters": {"q": q}, "row_count": len(items)},
    )

    filename = f"budget_adjustments_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/adjustments", response_model=BudgetAdjustmentResponse, status_code=201)
async def create_adjustment(
    body: BudgetAdjustmentCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    adjustment, target_email = await budget_service.create_adjustment(
        db,
        user_id=body.user_id,
        amount_cents=body.amount_cents,
        reason=body.reason,
        created_by=admin.id,
    )

    await log_admin_action(
        db, request, admin.id, "admin.budget.adjustment_created",
        resource_type="budget_adjustment", resource_id=adjustment.id,
        details={
            "target_user_id": str(body.user_id),
            "amount_cents": body.amount_cents,
            "reason": body.reason,
        },
    )

    if target_email:
        available = await budget_service.get_available_budget_cents(db, body.user_id)
        create_background_task(
            _send_budget_notification(
                target_email,
                body.amount_cents,
                body.reason,
                available,
            )
        )

    return adjustment


@router.put("/adjustments/{adjustment_id}", response_model=BudgetAdjustmentResponse)
async def update_adjustment(
    adjustment_id: UUID,
    body: BudgetAdjustmentUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    adjustment, old_data, enriched = await budget_service.update_adjustment(
        db, adjustment_id, amount_cents=body.amount_cents, reason=body.reason,
    )

    await log_admin_action(
        db, request, admin.id, "admin.budget.adjustment_updated",
        resource_type="budget_adjustment", resource_id=adjustment.id,
        details={
            "target_user_id": str(adjustment.user_id),
            "old_amount_cents": old_data["amount_cents"],
            "new_amount_cents": body.amount_cents,
            "old_reason": old_data["reason"],
            "new_reason": body.reason,
        },
    )
    return enriched


@router.delete("/adjustments/{adjustment_id}", status_code=204)
async def delete_adjustment(
    adjustment_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    _, details = await budget_service.delete_adjustment(db, adjustment_id)

    await log_admin_action(
        db, request, admin.id, "admin.budget.adjustment_deleted",
        resource_type="budget_adjustment", resource_id=adjustment_id,
        details=details,
    )
    return Response(status_code=204)
