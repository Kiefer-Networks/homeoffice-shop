from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.models.dto.product import (
    AmazonProductResponse,
    AmazonSearchResponse,
)
from src.models.orm.user import User
from src.services import amazon_service

router = APIRouter(prefix="/amazon", tags=["admin-amazon"])


@router.get("/search", response_model=list[AmazonSearchResponse])
async def amazon_search(
    query: str = Query(min_length=1, max_length=200),
    admin: User = Depends(require_staff),
):
    results = await amazon_service.search_products(query)
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
    request: Request,
    asin: str = Query(min_length=10, max_length=10),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await amazon_service.get_product(asin)
    if not product:
        return AmazonProductResponse(name="", description=None)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.amazon.product_lookup",
        resource_type="amazon", details={"asin": asin},
        ip_address=ip, user_agent=ua,
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
        variants=[v.model_dump() for v in product.variants],
    )
