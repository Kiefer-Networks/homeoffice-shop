import logging
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import log_admin_action
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.dto.order import (
    OrderHiBobSyncResponse,
    OrderHiBobUnsyncResponse,
    OrderItemCheckResponse,
    OrderItemCheckUpdate,
    OrderInvoiceResponse,
    OrderListResponse,
    OrderPurchaseUrlUpdate,
    OrderResponse,
    OrderStatusUpdate,
    OrderTrackingInfoUpdate,
)
from src.models.orm.order import Order
from src.models.orm.user import User
from src.services import order_service
from src.services.hibob_order_sync import sync_order_to_hibob, unsync_order_from_hibob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["admin-orders"])


@router.get("", response_model=OrderListResponse)
async def list_all_orders(
    status: Literal["pending", "ordered", "delivered", "rejected", "cancelled"] | None = None,
    q: str | None = Query(None, max_length=200),
    sort: Literal["newest", "oldest", "total_asc", "total_desc"] | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    items, total = await order_service.get_orders(
        db, status=status, q=q, sort=sort, page=page, per_page=per_page,
        include_invoices=True,
    )
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    data = await order_service.get_order_with_items(
        db, order_id, include_invoices=True, include_tracking_updates=True
    )
    if not data:
        raise NotFoundError("Order not found")
    return data


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: UUID,
    body: OrderStatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    pre_data = await order_service.get_order_with_items(db, order_id)
    old_status = pre_data["status"] if pre_data else None

    order = await order_service.transition_order(
        db, order_id, body.status, admin.id, body.admin_note,
        expected_delivery=body.expected_delivery,
        purchase_url=body.purchase_url,
        tracking_number=body.tracking_number,
        tracking_url=body.tracking_url,
    )

    await log_admin_action(
        db, request, admin.id, "admin.order.status_changed",
        resource_type="order", resource_id=order.id,
        details={
            "old_status": old_status,
            "new_status": body.status,
            "admin_note": body.admin_note,
            "expected_delivery": body.expected_delivery,
            "purchase_url": body.purchase_url,
            "tracking_number": body.tracking_number,
            "tracking_url": body.tracking_url,
            "order_user_id": str(order.user_id),
            "order_user_email": pre_data.get("user_email") if pre_data else None,
            "order_total_cents": order.total_cents,
        },
    )

    order_data = await order_service.get_order_with_items(
        db, order_id, include_invoices=True, include_tracking_updates=True
    )

    try:
        await order_service.notify_status_changed(
            db, order, order_data, body.status, body.admin_note,
        )
    except Exception:
        logger.exception("Failed to send status notification for order %s", order_id)

    return order_data


@router.put("/{order_id}/purchase-url", response_model=OrderResponse)
async def update_purchase_url(
    order_id: UUID,
    body: OrderPurchaseUrlUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    await order_service.update_purchase_url(db, order_id, body.purchase_url)

    await log_admin_action(
        db, request, admin.id, "admin.order.purchase_url_updated",
        resource_type="order", resource_id=order_id,
        details={"purchase_url": body.purchase_url},
    )

    order_data = await order_service.get_order_with_items(db, order_id, include_invoices=True)
    return order_data


@router.put("/{order_id}/tracking", response_model=OrderResponse)
async def update_order_tracking(
    order_id: UUID,
    body: OrderTrackingInfoUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    order = await order_service.update_tracking_info(
        db, order_id, admin.id,
        tracking_number=body.tracking_number,
        tracking_url=body.tracking_url,
        comment=body.comment,
    )

    await log_admin_action(
        db, request, admin.id, "admin.order.tracking_updated",
        resource_type="order", resource_id=order.id,
        details={
            "tracking_number": body.tracking_number,
            "tracking_url": body.tracking_url,
            "comment": body.comment,
            "order_user_id": str(order.user_id),
        },
    )

    order_data = await order_service.get_order_with_items(
        db, order_id, include_invoices=True, include_tracking_updates=True
    )

    try:
        await order_service.notify_tracking_update(
            db, order, order_data, body.comment,
        )
    except Exception:
        logger.exception("Failed to send tracking notification for order %s", order_id)

    return order_data


@router.post("/{order_id}/aftership-sync")
async def sync_aftership_tracking(
    order_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    """Manually trigger an AfterShip sync for this order."""
    from src.integrations.aftership.sync import sync_order_tracking
    from src.integrations.aftership.client import aftership_client

    if not aftership_client.is_configured:
        raise BadRequestError("AfterShip is not configured")

    order_result = await db.execute(
        select(Order).where(Order.id == order_id)
    )
    order = order_result.scalar_one_or_none()
    if not order:
        raise NotFoundError("Order not found")

    if not order.aftership_tracking_id:
        # Try to register first
        if order.tracking_number:
            await order_service._register_aftership_tracking(db, order)
            await db.flush()
        if not order.aftership_tracking_id:
            raise BadRequestError("No AfterShip tracking registered for this order")

    transitioned = await sync_order_tracking(db, order)

    await log_admin_action(
        db, request, admin.id, "admin.order.aftership_synced",
        resource_type="order", resource_id=order.id,
        details={
            "tracking_number": order.tracking_number,
            "tracking_url": order.tracking_url,
            "aftership_tracking_id": order.aftership_tracking_id,
            "aftership_slug": order.aftership_slug,
            "order_status": order.status,
            "auto_delivered": transitioned,
            "order_user_id": str(order.user_id),
            "order_total_cents": order.total_cents,
            "trigger": "manual",
        },
    )

    order_data = await order_service.get_order_with_items(
        db, order_id, include_invoices=True, include_tracking_updates=True
    )
    return order_data


@router.post("/{order_id}/invoices", response_model=OrderInvoiceResponse, status_code=201)
async def upload_invoice(
    order_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    content = await file.read()
    filename = file.filename or "upload"

    invoice = await order_service.upload_invoice(
        db, order_id, filename, content, file.content_type, admin.id,
    )

    await log_admin_action(
        db, request, admin.id, "admin.order.invoice_uploaded",
        resource_type="order", resource_id=order_id,
        details={
            "filename": filename,
            "invoice_id": str(invoice.id),
            "file_size_bytes": len(content),
            "content_type": file.content_type,
        },
    )

    return invoice


@router.get("/{order_id}/invoices/{invoice_id}/download")
async def download_invoice(
    order_id: UUID,
    invoice_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    invoice = await order_service.get_invoice(db, order_id, invoice_id)

    await log_admin_action(
        db, request, admin.id, "admin.order.invoice_downloaded",
        resource_type="order", resource_id=order_id,
        details={"invoice_id": str(invoice_id), "filename": invoice.filename},
    )

    safe_name = invoice.filename.encode("ascii", "replace").decode()
    encoded_name = quote(invoice.filename)
    return FileResponse(
        path=invoice.file_path,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_name}"; '
                f"filename*=UTF-8''{encoded_name}"
            ),
        },
    )


@router.delete("/{order_id}/invoices/{invoice_id}", status_code=204)
async def delete_invoice(
    order_id: UUID,
    invoice_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    await order_service.delete_invoice(db, order_id, invoice_id)

    await log_admin_action(
        db, request, admin.id, "admin.order.invoice_deleted",
        resource_type="order", resource_id=order_id,
        details={"invoice_id": str(invoice_id)},
    )

    return Response(status_code=204)


@router.put("/{order_id}/items/{item_id}/check", response_model=OrderItemCheckResponse)
async def check_order_item(
    order_id: UUID,
    item_id: UUID,
    body: OrderItemCheckUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    item = await order_service.update_order_item_check(db, order_id, item_id, body.vendor_ordered)
    if not item:
        raise NotFoundError("Order item not found")

    await log_admin_action(
        db, request, admin.id, "admin.order.item_checked",
        resource_type="order_item", resource_id=item.id,
        details={
            "order_id": str(order_id),
            "vendor_ordered": body.vendor_ordered,
            "product_id": str(item.product_id),
        },
    )
    return {"detail": "Item updated", "vendor_ordered": item.vendor_ordered}


@router.post("/{order_id}/sync-hibob", response_model=OrderHiBobSyncResponse)
async def sync_order_hibob(
    order_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    try:
        entries_created = await sync_order_to_hibob(db, order_id, admin.id)
    except ValueError as e:
        raise BadRequestError(str(e))

    order_data = await order_service.get_order_with_items(db, order_id, include_invoices=True)

    item_summaries = [
        {"product": i.get("product_name"), "qty": i.get("quantity"), "price_cents": i.get("price_cents")}
        for i in (order_data.get("items") or [])
    ] if order_data else []
    await log_admin_action(
        db, request, admin.id, "admin.order.hibob_synced",
        resource_type="order", resource_id=order_id,
        details={
            "entries_created": entries_created,
            "order_user_id": str(order_data["user_id"]) if order_data else None,
            "order_user_email": order_data.get("user_email") if order_data else None,
            "order_total_cents": order_data.get("total_cents") if order_data else None,
            "items_synced": item_summaries,
        },
    )

    return {
        "detail": f"Synced {entries_created} item{'s' if entries_created != 1 else ''} to HiBob",
        "synced_at": order_data.get("hibob_synced_at") if order_data else None,
        "order": order_data,
    }


@router.delete("/{order_id}/sync-hibob", response_model=OrderHiBobUnsyncResponse)
async def unsync_order_hibob(
    order_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    pre_data = await order_service.get_order_with_items(db, order_id)

    try:
        entries_deleted = await unsync_order_from_hibob(db, order_id, admin.id)
    except ValueError as e:
        raise BadRequestError(str(e))

    item_summaries = [
        {"product": i.get("product_name"), "qty": i.get("quantity"), "price_cents": i.get("price_cents")}
        for i in (pre_data.get("items") or [])
    ] if pre_data else []
    await log_admin_action(
        db, request, admin.id, "admin.order.hibob_unsynced",
        resource_type="order", resource_id=order_id,
        details={
            "entries_deleted": entries_deleted,
            "order_user_id": str(pre_data["user_id"]) if pre_data else None,
            "order_user_email": pre_data.get("user_email") if pre_data else None,
            "order_total_cents": pre_data.get("total_cents") if pre_data else None,
            "items_unsynced": item_summaries,
        },
    )

    order_data = await order_service.get_order_with_items(db, order_id, include_invoices=True)
    return {
        "detail": f"Removed {entries_deleted} entr{'y' if entries_deleted == 1 else 'ies'} from HiBob",
        "order": order_data,
    }
