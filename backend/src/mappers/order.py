from src.models.orm.order import Order, OrderInvoice, OrderItem
from src.models.orm.user import User


def order_item_to_dict(item: OrderItem, product_name: str | None) -> dict:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "product_name": product_name,
        "quantity": item.quantity,
        "price_cents": item.price_cents,
        "external_url": item.external_url,
        "vendor_ordered": item.vendor_ordered,
        "variant_asin": item.variant_asin,
        "variant_value": item.variant_value,
    }


def invoice_to_dict(invoice: OrderInvoice) -> dict:
    return {
        "id": invoice.id,
        "filename": invoice.filename,
        "uploaded_by": invoice.uploaded_by,
        "uploaded_at": invoice.uploaded_at,
    }


def order_to_dict(
    order: Order,
    user: User | None,
    items: list[dict],
    invoices: list[dict] | None = None,
) -> dict:
    return {
        "id": order.id,
        "user_id": order.user_id,
        "user_email": user.email if user else None,
        "user_display_name": user.display_name if user else None,
        "status": order.status,
        "total_cents": order.total_cents,
        "delivery_note": order.delivery_note,
        "admin_note": order.admin_note,
        "expected_delivery": order.expected_delivery,
        "purchase_url": order.purchase_url,
        "reviewed_by": order.reviewed_by,
        "reviewed_at": order.reviewed_at,
        "cancellation_reason": order.cancellation_reason,
        "cancelled_by": order.cancelled_by,
        "cancelled_at": order.cancelled_at,
        "items": items,
        "invoices": invoices or [],
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "hibob_synced_at": order.hibob_synced_at,
    }
