import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.models.orm.category import Category
from src.models.orm.hibob_purchase_review import HiBobPurchaseReview
from src.models.orm.order import Order
from src.models.orm.product import Product
from src.models.orm.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["admin-dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    """Return aggregate counts for the admin dashboard using optimized grouped queries."""
    # Orders: single query with FILTER for all order-related counts
    order_result = await db.execute(
        select(
            func.count(Order.id).label("total_orders"),
            func.count(Order.id).filter(Order.status == "pending").label("pending_orders"),
            func.count(Order.id).filter(Order.status == "ordered").label("ordered_orders"),
            func.count(Order.id).filter(Order.status == "delivered").label("delivered_orders"),
        ).select_from(Order)
    )
    order_row = order_result.one()

    # Products: single query with FILTER
    product_result = await db.execute(
        select(
            func.count(Product.id).label("total_products"),
            func.count(Product.id).filter(
                Product.is_active.is_(True), Product.archived_at.is_(None)
            ).label("active_products"),
        ).select_from(Product)
    )
    product_row = product_result.one()

    # Users + categories + reviews: single query each (no FILTER grouping possible)
    total_employees = (
        await db.execute(
            select(func.count()).select_from(User).where(User.role == "employee")
        )
    ).scalar() or 0

    pending_reviews = (
        await db.execute(
            select(func.count())
            .select_from(HiBobPurchaseReview)
            .where(HiBobPurchaseReview.status == "pending")
        )
    ).scalar() or 0

    total_categories = (
        await db.execute(select(func.count()).select_from(Category))
    ).scalar() or 0

    return {
        "pending_orders": order_row.pending_orders or 0,
        "ordered_orders": order_row.ordered_orders or 0,
        "delivered_orders": order_row.delivered_orders or 0,
        "total_orders": order_row.total_orders or 0,
        "total_products": product_row.total_products or 0,
        "active_products": product_row.active_products or 0,
        "total_employees": total_employees,
        "pending_reviews": pending_reviews,
        "total_categories": total_categories,
    }
