from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import BadRequestError, NotFoundError
from src.integrations.amazon.client import AmazonClient
from src.services.image_service import download_and_store_product_images
from src.models.dto.product import ProductCreate, ProductUpdate
from src.models.orm.product import Product
from src.models.orm.user import User

router = APIRouter(prefix="/products", tags=["admin-products"])

UPLOAD_DIR = Path("/app/uploads")
if not UPLOAD_DIR.exists():
    UPLOAD_DIR = Path("uploads")
    UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("")
async def create_product(
    body: ProductCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if body.price_cents == 0:
        body.is_active = False

    product = Product(
        category_id=body.category_id,
        name=body.name,
        description=body.description,
        brand=body.brand,
        model=body.model,
        price_cents=body.price_cents,
        amazon_asin=body.amazon_asin,
        external_url=body.external_url,
        is_active=body.is_active,
        max_quantity_per_user=body.max_quantity_per_user,
    )
    db.add(product)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.created",
        resource_type="product", resource_id=product.id,
        details={"name": product.name}, ip_address=ip,
    )

    return product


@router.put("/{product_id}")
async def update_product(
    product_id: UUID,
    body: ProductUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")

    changes = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        old_value = getattr(product, field)
        if old_value != value:
            changes[field] = {"old": old_value, "new": value}
            setattr(product, field, value)

    if product.price_cents == 0 and product.is_active:
        product.is_active = False
        changes["is_active"] = {"old": True, "new": False}

    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.updated",
        resource_type="product", resource_id=product.id,
        details=changes, ip_address=ip,
    )

    return product


@router.post("/{product_id}/activate")
async def activate_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    if product.price_cents == 0:
        raise BadRequestError("Cannot activate product with price 0")
    product.is_active = True
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.activated",
        resource_type="product", resource_id=product.id, ip_address=ip,
    )
    return product


@router.post("/{product_id}/deactivate")
async def deactivate_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    product.is_active = False
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.deactivated",
        resource_type="product", resource_id=product.id, ip_address=ip,
    )
    return product


@router.post("/{product_id}/redownload-images")
async def redownload_images(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    if not product.amazon_asin:
        raise BadRequestError("Product has no Amazon ASIN")

    client = AmazonClient()
    amazon_data = await client.get_product(product.amazon_asin)
    if not amazon_data:
        raise BadRequestError("Amazon lookup returned no data")

    main_image = amazon_data.images[0] if amazon_data.images else None
    gallery = amazon_data.images[1:] if len(amazon_data.images) > 1 else []

    paths = await download_and_store_product_images(
        product.id,
        main_image,
        gallery,
        UPLOAD_DIR,
        product.name,
    )

    product.image_url = paths.main_image
    product.image_gallery = paths.gallery
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.images_redownloaded",
        resource_type="product", resource_id=product.id, ip_address=ip,
    )

    return {"image_url": product.image_url, "image_gallery": product.image_gallery}
