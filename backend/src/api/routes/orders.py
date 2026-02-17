from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import NotFoundError
from src.models.dto.order import OrderCreate, OrderListResponse, OrderResponse
from src.models.orm.user import User
from src.notifications.service import notify_admins_email, notify_admins_slack
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


@router.post("", response_model=OrderResponse)
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

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=user.id, action="order.created",
        resource_type="order", resource_id=order.id,
        details={"total_cents": order.total_cents},
        ip_address=ip,
    )

    if body.confirm_price_changes:
        await write_audit_log(
            db, user_id=user.id, action="order.price_change_confirmed",
            resource_type="order", resource_id=order.id,
            ip_address=ip,
        )

    order_data = await order_service.get_order_with_items(db, order.id)

    from src.core.config import settings
    await notify_admins_email(
        db, event="order.created",
        subject=f"New Order from {user.display_name}",
        template_name="order_created.html",
        context={
            "user_name": user.display_name,
            "user_email": user.email,
            "items": order_data["items"] if order_data else [],
            "total_cents": order.total_cents,
            "delivery_note": order.delivery_note,
            "admin_url": f"{settings.frontend_url}/admin/orders/{order.id}",
        },
    )
    await notify_admins_slack(
        db, event="order.created",
        text=f"New order from {user.display_name} ({user.email}) - Total: EUR {order.total_cents / 100:.2f}",
    )

    return order_data
