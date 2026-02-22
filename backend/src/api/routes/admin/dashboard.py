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
    """Return aggregate counts for the admin dashboard in a single query batch."""
    pending_orders = (
        await db.execute(
            select(func.count()).select_from(Order).where(Order.status == "pending")
        )
    ).scalar() or 0

    total_orders = (
        await db.execute(select(func.count()).select_from(Order))
    ).scalar() or 0

    total_products = (
        await db.execute(select(func.count()).select_from(Product))
    ).scalar() or 0

    active_products = (
        await db.execute(
            select(func.count())
            .select_from(Product)
            .where(Product.is_active.is_(True), Product.archived_at.is_(None))
        )
    ).scalar() or 0

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
        "pending_orders": pending_orders,
        "total_orders": total_orders,
        "total_products": total_products,
        "active_products": active_products,
        "total_employees": total_employees,
        "pending_reviews": pending_reviews,
        "total_categories": total_categories,
    }
