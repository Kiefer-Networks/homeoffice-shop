import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.config import settings
from src.core.exceptions import BadRequestError, NotFoundError
from src.models.dto import DetailResponse
from src.integrations.amazon.client import AmazonClient
from src.services.image_service import download_and_store_product_images
from src.models.dto.product import ProductCreate, ProductResponse, ProductUpdate
from src.models.orm.brand import Brand
from src.models.orm.product import Product
from src.models.orm.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["admin-products"])


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    if body.price_cents == 0:
        body.is_active = False

    # Auto-create or lookup Brand if brand text provided without brand_id
    brand_id = body.brand_id
    if body.brand and not brand_id:
        result = await db.execute(
            select(Brand).where(Brand.name == body.brand)
        )
        existing_brand = result.scalar_one_or_none()
        if existing_brand:
            brand_id = existing_brand.id
        else:
            slug = body.brand.lower().replace(" ", "-").replace(".", "")
            new_brand = Brand(name=body.brand, slug=slug)
            db.add(new_brand)
            await db.flush()
            brand_id = new_brand.id

    product = Product(
        category_id=body.category_id,
        name=body.name,
        description=body.description,
        brand=body.brand,
        brand_id=brand_id,
        model=body.model,
        price_cents=body.price_cents,
        amazon_asin=body.amazon_asin,
        external_url=body.external_url,
        is_active=body.is_active,
        max_quantity_per_user=body.max_quantity_per_user,
    )
    db.add(product)
    await db.flush()

    if product.amazon_asin:
        try:
            client = AmazonClient()
            amazon_data = await client.get_product(product.amazon_asin)
            if amazon_data:
                main_image = amazon_data.images[0] if amazon_data.images else None
                gallery = amazon_data.images[1:] if len(amazon_data.images) > 1 else []

                paths = await download_and_store_product_images(
                    product.id, main_image, gallery, settings.upload_dir, product.name,
                )
                product.image_url = paths.main_image
                product.image_gallery = paths.gallery

                if amazon_data.specifications:
                    product.specifications = amazon_data.specifications
                if amazon_data.brand:
                    product.brand = amazon_data.brand

                product.color = amazon_data.color
                product.material = amazon_data.material
                product.product_dimensions = amazon_data.product_dimensions
                product.item_weight = amazon_data.item_weight
                product.item_model_number = amazon_data.item_model_number
                product.product_information = amazon_data.product_information

                await db.flush()
        except Exception:
            logger.exception("Failed to auto-download images for product %s", product.id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.created",
        resource_type="product", resource_id=product.id,
        details={"name": product.name}, ip_address=ip,
    )

    await db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    body: ProductUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
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

    await db.refresh(product)
    return product


@router.post("/{product_id}/activate", response_model=ProductResponse)
async def activate_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
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
    await db.refresh(product)
    return product


@router.post("/{product_id}/deactivate", response_model=ProductResponse)
async def deactivate_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
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
    await db.refresh(product)
    return product


@router.delete("/{product_id}", response_model=ProductResponse)
async def archive_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")

    product.archived_at = datetime.now(timezone.utc)
    product.is_active = False
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.archived",
        resource_type="product", resource_id=product_id,
        details={"name": product.name}, ip_address=ip,
    )
    await db.refresh(product)
    return product


@router.post("/{product_id}/restore", response_model=ProductResponse)
async def restore_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    if not product.archived_at:
        raise BadRequestError("Product is not archived")

    product.archived_at = None
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.restored",
        resource_type="product", resource_id=product_id,
        details={"name": product.name}, ip_address=ip,
    )
    await db.refresh(product)
    return product


@router.post("/{product_id}/redownload-images", response_model=ProductResponse)
async def redownload_images(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await db.get(Product, product_id)
    if not product:
        raise NotFoundError("Product not found")
    if not product.amazon_asin:
        raise BadRequestError("Product has no Amazon ASIN")

    try:
        client = AmazonClient()
        amazon_data = await client.get_product(product.amazon_asin)
    except Exception:
        logger.exception("ScraperAPI call failed for ASIN %s", product.amazon_asin)
        raise BadRequestError("Amazon API request failed. Please try again later.")

    if not amazon_data:
        raise BadRequestError("Amazon lookup returned no data")

    main_image = amazon_data.images[0] if amazon_data.images else None
    gallery = amazon_data.images[1:] if len(amazon_data.images) > 1 else []

    try:
        paths = await download_and_store_product_images(
            product.id,
            main_image,
            gallery,
            settings.upload_dir,
            product.name,
        )
        product.image_url = paths.main_image
        product.image_gallery = paths.gallery
    except Exception as exc:
        logger.exception("Image download failed for product %s", product.id)
        raise BadRequestError(f"Failed to download images: {exc}")

    # Update product information fields from Amazon data
    product.color = amazon_data.color
    product.material = amazon_data.material
    product.product_dimensions = amazon_data.product_dimensions
    product.item_weight = amazon_data.item_weight
    product.item_model_number = amazon_data.item_model_number
    product.product_information = amazon_data.product_information
    if amazon_data.brand:
        product.brand = amazon_data.brand

    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.images_redownloaded",
        resource_type="product", resource_id=product.id, ip_address=ip,
    )

    await db.refresh(product)
    return product
