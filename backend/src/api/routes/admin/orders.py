from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.dto import DetailResponse
from src.models.dto.order import OrderItemCheckUpdate, OrderListResponse, OrderResponse, OrderStatusUpdate
from src.models.orm.user import User
from src.notifications.service import notify_admins_slack, notify_user_email
from src.services import order_service

router = APIRouter(prefix="/orders", tags=["admin-orders"])


VALID_STATUSES = {"pending", "ordered", "delivered", "rejected", "cancelled"}


@router.get("", response_model=OrderListResponse)
async def list_all_orders(
    status: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if status and status not in VALID_STATUSES:
        raise BadRequestError(f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
    items, total = await order_service.get_orders(
        db, status=status, page=page, per_page=per_page
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    data = await order_service.get_order_with_items(db, order_id)
    if not data:
        raise NotFoundError("Order not found")
    return data


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    body: OrderStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    order = await order_service.transition_order(
        db, order_id, body.status, admin.id, body.admin_note
    )

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.status_changed",
        resource_type="order", resource_id=order.id,
        details={"new_status": body.status, "admin_note": body.admin_note},
        ip_address=ip,
    )

    order_data = await order_service.get_order_with_items(db, order_id)

    if order_data and order_data.get("user_email"):
        from src.core.config import settings
        await notify_user_email(
            order_data["user_email"],
            subject=f"Order Status Updated: {body.status.title()}",
            template_name="order_status_changed.html",
            context={
                "order_id_short": str(order.id)[:8],
                "new_status": body.status,
                "admin_note": body.admin_note,
                "items": order_data.get("items", []),
                "total_cents": order.total_cents,
            },
        )

    if body.status == "cancelled":
        await notify_admins_slack(
            db, event="order.cancelled",
            text=f"Order {str(order.id)[:8]} has been cancelled.",
        )

    if body.status != "cancelled":
        await notify_admins_slack(
            db, event="order.status_changed",
            text=f"Order {str(order.id)[:8]} status changed to {body.status}.",
        )

    return order_data


@router.put("/{order_id}/items/{item_id}/check")
async def check_order_item(
    order_id: UUID,
    item_id: UUID,
    body: OrderItemCheckUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    item = await order_service.update_order_item_check(db, order_id, item_id, body.vendor_ordered)
    if not item:
        raise NotFoundError("Order item not found")

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.item_checked",
        resource_type="order_item", resource_id=item.id,
        details={"vendor_ordered": body.vendor_ordered},
        ip_address=ip,
    )
    return {"detail": "Item updated", "vendor_ordered": item.vendor_ordered}
