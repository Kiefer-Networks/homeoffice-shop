from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.core.exceptions import NotFoundError
from src.models.dto.order import OrderCancelRequest, OrderCreate, OrderListResponse, OrderResponse
from src.models.orm.user import User
from src.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=OrderListResponse)
async def list_my_orders(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items, total = await order_service.get_orders(
        db, user_id=user.id, page=page, per_page=per_page
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/{order_id}", response_model=OrderResponse)
async def get_my_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order_data = await order_service.get_order_with_items(db, order_id)
    if not order_data or order_data["user_id"] != user.id:
        raise NotFoundError("Order not found")
    return order_data


@router.post("", response_model=OrderResponse, status_code=201)
async def create_order(
    body: OrderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await order_service.create_order_from_cart(
        db,
        user.id,
        delivery_note=body.delivery_note,
        confirm_price_changes=body.confirm_price_changes,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=user.id, action="order.created",
        resource_type="order", resource_id=order.id,
        details={
            "total_cents": order.total_cents,
            "delivery_note": order.delivery_note,
        },
        ip_address=ip, user_agent=ua,
    )

    if body.confirm_price_changes:
        await write_audit_log(
            db, user_id=user.id, action="order.price_change_confirmed",
            resource_type="order", resource_id=order.id,
            ip_address=ip, user_agent=ua,
        )

    order_data = await order_service.get_order_with_items(db, order.id)

    await order_service.notify_order_created(db, order, user, order_data)

    return order_data


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_my_order(
    order_id: UUID,
    body: OrderCancelRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = await order_service.cancel_order_by_user(
        db, order_id, user.id, body.reason
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=user.id, action="order.cancelled",
        resource_type="order", resource_id=order.id,
        details={"reason": body.reason, "total_cents": order.total_cents},
        ip_address=ip, user_agent=ua,
    )

    await order_service.notify_order_cancelled_by_user(db, order, user, body.reason)

    order_data = await order_service.get_order_with_items(db, order.id)
    return order_data
