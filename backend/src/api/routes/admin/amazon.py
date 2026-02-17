from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.integrations.amazon.client import AmazonClient
from src.models.dto.product import (
    AmazonProductResponse,
    AmazonSearchResponse,
)
from src.models.orm.user import User

router = APIRouter(prefix="/amazon", tags=["admin-amazon"])


@router.get("/search", response_model=list[AmazonSearchResponse])
async def amazon_search(
    query: str = Query(min_length=1, max_length=200),
    admin: User = Depends(require_admin),
):
    client = AmazonClient()
    results = await client.search(query)
    return [
        AmazonSearchResponse(
            name=r.name,
            asin=r.asin,
            price_cents=r.price_cents,
            image_url=r.image_url,
            url=r.url,
            rating=r.rating,
            reviews=r.reviews,
        )
        for r in results
    ]


@router.get("/product", response_model=AmazonProductResponse)
async def amazon_product(
    asin: str = Query(min_length=10, max_length=10),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    client = AmazonClient()
    product = await client.get_product(asin)
    if not product:
        return AmazonProductResponse(name="", description=None)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.amazon.product_lookup",
        resource_type="amazon", details={"asin": asin}, ip_address=ip,
    )

    return AmazonProductResponse(
        name=product.name,
        description=product.description,
        brand=product.brand,
        images=product.images,
        price_cents=product.price_cents,
        specifications=product.specifications,
        feature_bullets=product.feature_bullets,
        url=product.url,
    )
