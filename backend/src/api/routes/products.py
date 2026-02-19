from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.core.exceptions import BadRequestError, NotFoundError

VALID_SORTS = {"relevance", "price_asc", "price_desc", "name_asc", "name_desc", "newest"}
from src.models.dto.product import ProductListResponse, ProductResponse
from src.models.orm.product import Product
from src.models.orm.user import User
from src.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    q: str | None = Query(None, max_length=200),
    category: UUID | None = None,
    brand: str | None = None,
    color: str | None = None,
    material: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    sort: str = "relevance",
    include_archived: bool = False,
    archived_only: bool = False,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if sort not in VALID_SORTS:
        raise BadRequestError(f"Invalid sort. Must be one of: {', '.join(sorted(VALID_SORTS))}")
    result = await product_service.search_products(
        db,
        q=q,
        category_id=category,
        brand=brand,
        color=color,
        material=material,
        price_min=price_min,
        price_max=price_max,
        include_archived=include_archived,
        archived_only=archived_only,
        sort=sort,
        page=page,
        per_page=per_page,
    )
    result["items"] = [
        ProductResponse.model_validate(p) for p in result["items"]
    ]
    return result


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    return product
