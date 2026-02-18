import asyncio
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.config import settings
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.dto import DetailResponse
from src.models.dto.order import (
    OrderItemCheckUpdate,
    OrderInvoiceResponse,
    OrderListResponse,
    OrderPurchaseUrlUpdate,
    OrderResponse,
    OrderStatusUpdate,
)
from src.models.orm.user import User
from src.notifications.service import notify_staff_slack, notify_user_email
from src.services import order_service

router = APIRouter(prefix="/orders", tags=["admin-orders"])


VALID_STATUSES = {"pending", "ordered", "delivered", "rejected", "cancelled"}
ALLOWED_INVOICE_TYPES = {"application/pdf", "image/jpeg", "image/png"}
ALLOWED_INVOICE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_INVOICE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.get("", response_model=OrderListResponse)
async def list_all_orders(
    status: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    if status and status not in VALID_STATUSES:
        raise BadRequestError(f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}")
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
    data = await order_service.get_order_with_items(db, order_id, include_invoices=True)
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
    order = await order_service.transition_order(
        db, order_id, body.status, admin.id, body.admin_note,
        expected_delivery=body.expected_delivery,
        purchase_url=body.purchase_url,
    )

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.status_changed",
        resource_type="order", resource_id=order.id,
        details={"new_status": body.status, "admin_note": body.admin_note},
        ip_address=ip,
    )

    order_data = await order_service.get_order_with_items(db, order_id, include_invoices=True)

    if order_data and order_data.get("user_email"):
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
        await notify_staff_slack(
            db, event="order.cancelled",
            text=f"Order {str(order.id)[:8]} has been cancelled.",
        )
    else:
        await notify_staff_slack(
            db, event="order.status_changed",
            text=f"Order {str(order.id)[:8]} status changed to {body.status}.",
        )

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

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.purchase_url_updated",
        resource_type="order", resource_id=order_id,
        details={"purchase_url": body.purchase_url},
        ip_address=ip,
    )

    order_data = await order_service.get_order_with_items(db, order_id, include_invoices=True)
    return order_data


@router.post("/{order_id}/invoices", response_model=OrderInvoiceResponse, status_code=201)
async def upload_invoice(
    order_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    # Validate file type
    if file.content_type not in ALLOWED_INVOICE_TYPES:
        raise BadRequestError(
            f"Invalid file type. Allowed: PDF, JPEG, PNG"
        )

    # Validate extension
    filename = file.filename or "upload"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_INVOICE_EXTENSIONS:
        raise BadRequestError(
            f"Invalid file extension. Allowed: {', '.join(ALLOWED_INVOICE_EXTENSIONS)}"
        )

    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_INVOICE_SIZE_BYTES:
        raise BadRequestError(
            f"File too large. Maximum size is {MAX_INVOICE_SIZE_BYTES // (1024 * 1024)} MB"
        )

    # Create directory
    invoice_dir = settings.upload_dir / "invoices" / str(order_id)
    invoice_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    stored_name = f"{uuid.uuid4()}{ext}"
    file_path = invoice_dir / stored_name

    # Write file (non-blocking)
    await asyncio.to_thread(file_path.write_bytes, content)

    invoice = await order_service.add_invoice(
        db, order_id, filename, str(file_path), admin.id
    )

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.invoice_uploaded",
        resource_type="order", resource_id=order_id,
        details={"filename": filename, "invoice_id": str(invoice.id)},
        ip_address=ip,
    )

    return invoice


@router.get("/{order_id}/invoices/{invoice_id}/download")
async def download_invoice(
    order_id: UUID,
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    from sqlalchemy import select as sa_select
    from src.models.orm.order import OrderInvoice

    result = await db.execute(
        sa_select(OrderInvoice).where(
            OrderInvoice.id == invoice_id,
            OrderInvoice.order_id == order_id,
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise NotFoundError("Invoice not found")

    file_path = Path(invoice.file_path).resolve()
    upload_root = settings.upload_dir.resolve()

    # Prevent path traversal
    if not file_path.is_relative_to(upload_root):
        raise BadRequestError("Invalid file path")

    if not file_path.exists():
        raise NotFoundError("Invoice file not found on disk")

    return FileResponse(
        path=str(file_path),
        filename=invoice.filename,
        media_type="application/octet-stream",
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

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.invoice_deleted",
        resource_type="order", resource_id=order_id,
        details={"invoice_id": str(invoice_id)},
        ip_address=ip,
    )

    return Response(status_code=204)


@router.put("/{order_id}/items/{item_id}/check")
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

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.item_checked",
        resource_type="order_item", resource_id=item.id,
        details={"vendor_ordered": body.vendor_ordered},
        ip_address=ip,
    )
    return {"detail": "Item updated", "vendor_ordered": item.vendor_ordered}
