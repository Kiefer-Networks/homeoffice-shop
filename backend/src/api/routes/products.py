from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import NotFoundError
from src.integrations.amazon.client import AmazonClient
from src.models.orm.product import Product
from src.models.orm.user import User
from src.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
async def list_products(
    q: str | None = None,
    category: UUID | None = None,
    brand: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    sort: str = "relevance",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await product_service.search_products(
        db,
        q=q,
        category_id=category,
        brand=brand,
        price_min=price_min,
        price_max=price_max,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    items = []
    for p in result["items"]:
        items.append({
            "id": p.id,
            "category_id": p.category_id,
            "name": p.name,
            "description": p.description,
            "brand": p.brand,
            "model": p.model,
            "image_url": p.image_url,
            "image_gallery": p.image_gallery,
            "specifications": p.specifications,
            "price_cents": p.price_cents,
            "price_min_cents": p.price_min_cents,
            "price_max_cents": p.price_max_cents,
            "amazon_asin": p.amazon_asin,
            "external_url": p.external_url,
            "is_active": p.is_active,
            "max_quantity_per_user": p.max_quantity_per_user,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })
    result["items"] = items
    return result


@router.get("/{product_id}")
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    return product


@router.post("/refresh-prices")
async def trigger_price_refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    client = AmazonClient()
    result = await product_service.refresh_all_prices(db, client)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=user.id, action="product.price_refresh_triggered",
        resource_type="product", details=result, ip_address=ip,
    )
    return result
