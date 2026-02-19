import asyncio
import uuid
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.core.config import settings
from src.core.exceptions import BadRequestError, NotFoundError
from src.integrations.hibob.client import HiBobClient
from src.models.dto import DetailResponse
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
)
from src.models.orm.user import User
from src.services import order_service
from src.services.hibob_order_sync import sync_order_to_hibob, unsync_order_from_hibob

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
    pre_data = await order_service.get_order_with_items(db, order_id)
    old_status = pre_data["status"] if pre_data else None

    order = await order_service.transition_order(
        db, order_id, body.status, admin.id, body.admin_note,
        expected_delivery=body.expected_delivery,
        purchase_url=body.purchase_url,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.status_changed",
        resource_type="order", resource_id=order.id,
        details={
            "old_status": old_status,
            "new_status": body.status,
            "admin_note": body.admin_note,
            "expected_delivery": body.expected_delivery,
            "purchase_url": body.purchase_url,
            "order_user_id": str(order.user_id),
            "order_user_email": pre_data.get("user_email") if pre_data else None,
            "order_total_cents": order.total_cents,
        },
        ip_address=ip, user_agent=ua,
    )

    order_data = await order_service.get_order_with_items(db, order_id, include_invoices=True)

    await order_service.notify_status_changed(
        db, order, order_data, body.status, body.admin_note,
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

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.purchase_url_updated",
        resource_type="order", resource_id=order_id,
        details={"purchase_url": body.purchase_url},
        ip_address=ip, user_agent=ua,
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

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.invoice_uploaded",
        resource_type="order", resource_id=order_id,
        details={
            "filename": filename,
            "invoice_id": str(invoice.id),
            "file_size_bytes": len(content),
            "content_type": file.content_type,
        },
        ip_address=ip, user_agent=ua,
    )

    return invoice


@router.get("/{order_id}/invoices/{invoice_id}/download")
async def download_invoice(
    order_id: UUID,
    invoice_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    invoice = await order_service.get_invoice(db, order_id, invoice_id)

    from urllib.parse import quote
    safe_name = invoice.filename.encode("ascii", "replace").decode()
    encoded_name = quote(invoice.filename)
    return FileResponse(
        path=str(Path(invoice.file_path).resolve()),
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

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.invoice_deleted",
        resource_type="order", resource_id=order_id,
        details={"invoice_id": str(invoice_id)},
        ip_address=ip, user_agent=ua,
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

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.item_checked",
        resource_type="order_item", resource_id=item.id,
        details={
            "order_id": str(order_id),
            "vendor_ordered": body.vendor_ordered,
            "product_id": str(item.product_id),
        },
        ip_address=ip, user_agent=ua,
    )
    return {"detail": "Item updated", "vendor_ordered": item.vendor_ordered}


@router.post("/{order_id}/sync-hibob", response_model=OrderHiBobSyncResponse)
async def sync_order_hibob(
    order_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    client = HiBobClient()
    try:
        entries_created = await sync_order_to_hibob(db, order_id, admin.id, client)
    except ValueError as e:
        raise BadRequestError(str(e))

    order_data = await order_service.get_order_with_items(db, order_id, include_invoices=True)

    ip, ua = audit_context(request)
    item_summaries = [
        {"product": i.get("product_name"), "qty": i.get("quantity"), "price_cents": i.get("price_cents")}
        for i in (order_data.get("items") or [])
    ] if order_data else []
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.hibob_synced",
        resource_type="order", resource_id=order_id,
        details={
            "entries_created": entries_created,
            "order_user_id": str(order_data["user_id"]) if order_data else None,
            "order_user_email": order_data.get("user_email") if order_data else None,
            "order_total_cents": order_data.get("total_cents") if order_data else None,
            "items_synced": item_summaries,
        },
        ip_address=ip, user_agent=ua,
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

    client = HiBobClient()
    try:
        entries_deleted = await unsync_order_from_hibob(db, order_id, admin.id, client)
    except ValueError as e:
        raise BadRequestError(str(e))

    ip, ua = audit_context(request)
    item_summaries = [
        {"product": i.get("product_name"), "qty": i.get("quantity"), "price_cents": i.get("price_cents")}
        for i in (pre_data.get("items") or [])
    ] if pre_data else []
    await write_audit_log(
        db, user_id=admin.id, action="admin.order.hibob_unsynced",
        resource_type="order", resource_id=order_id,
        details={
            "entries_deleted": entries_deleted,
            "order_user_id": str(pre_data["user_id"]) if pre_data else None,
            "order_user_email": pre_data.get("user_email") if pre_data else None,
            "order_total_cents": pre_data.get("total_cents") if pre_data else None,
            "items_unsynced": item_summaries,
        },
        ip_address=ip, user_agent=ua,
    )

    order_data = await order_service.get_order_with_items(db, order_id, include_invoices=True)
    return {
        "detail": f"Removed {entries_deleted} entr{'y' if entries_deleted == 1 else 'ies'} from HiBob",
        "order": order_data,
    }
