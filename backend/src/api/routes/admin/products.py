import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.core.config import settings
from src.core.exceptions import BadRequestError, NotFoundError
from src.integrations.amazon.client import AmazonClient
from src.services.image_service import download_and_store_product_images
from src.models.dto.product import (
    ProductCreate, ProductResponse, ProductUpdate,
    ProductFieldDiff, RefreshPreviewResponse, RefreshApplyRequest,
)
from src.models.orm.user import User
from src.services import product_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["admin-products"])

REFRESHABLE_FIELDS = {
    "name": "Name",
    "description": "Description",
    "brand": "Brand",
    "price_cents": "Price",
    "color": "Color",
    "material": "Material",
    "product_dimensions": "Dimensions",
    "item_weight": "Weight",
    "item_model_number": "Model Number",
    "specifications": "Specifications",
    "product_information": "Product Information",
    "variants": "Variants",
}


@router.post("", response_model=ProductResponse, status_code=201)
async def create_product(
    body: ProductCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await product_service.create_product(
        db,
        category_id=body.category_id,
        name=body.name,
        description=body.description,
        brand=body.brand,
        brand_id=body.brand_id,
        model=body.model,
        price_cents=body.price_cents,
        amazon_asin=body.amazon_asin,
        external_url=body.external_url,
        is_active=body.is_active,
        max_quantity_per_user=body.max_quantity_per_user,
    )

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

                if amazon_data.variants:
                    missing = [v.asin for v in amazon_data.variants if v.price_cents == 0]
                    if missing:
                        try:
                            prices = await client.get_variant_prices(missing)
                            for v in amazon_data.variants:
                                if v.asin in prices:
                                    v.price_cents = prices[v.asin]
                        except Exception:
                            logger.exception("Failed to fetch variant prices for product %s", product.id)

                    product.variants = [v.model_dump() for v in amazon_data.variants]
                    variant_prices = [v.price_cents for v in amazon_data.variants if v.price_cents > 0]
                    if variant_prices:
                        product.price_min_cents = min(variant_prices)
                        product.price_max_cents = max(variant_prices)

                await db.flush()
        except Exception:
            logger.exception("Failed to auto-download images for product %s", product.id)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.created",
        resource_type="product", resource_id=product.id,
        details={
            "name": product.name,
            "category_id": str(body.category_id) if body.category_id else None,
            "price_cents": body.price_cents,
            "amazon_asin": body.amazon_asin,
            "brand": body.brand,
        },
        ip_address=ip, user_agent=ua,
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
    product, changes = await product_service.update_product(
        db, product_id, body.model_dump(exclude_unset=True),
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.updated",
        resource_type="product", resource_id=product.id,
        details={"changes": changes, "product_name": product.name},
        ip_address=ip, user_agent=ua,
    )
    return product


@router.post("/{product_id}/activate", response_model=ProductResponse)
async def activate_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await product_service.set_active(db, product_id, True)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.activated",
        resource_type="product", resource_id=product.id,
        details={"product_name": product.name},
        ip_address=ip, user_agent=ua,
    )
    return product


@router.post("/{product_id}/deactivate", response_model=ProductResponse)
async def deactivate_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await product_service.set_active(db, product_id, False)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.deactivated",
        resource_type="product", resource_id=product.id,
        details={"product_name": product.name},
        ip_address=ip, user_agent=ua,
    )
    return product


@router.delete("/{product_id}", response_model=ProductResponse)
async def archive_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await product_service.archive(db, product_id)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.archived",
        resource_type="product", resource_id=product_id,
        details={"name": product.name},
        ip_address=ip, user_agent=ua,
    )
    return product


@router.post("/{product_id}/restore", response_model=ProductResponse)
async def restore_product(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await product_service.restore(db, product_id)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.restored",
        resource_type="product", resource_id=product_id,
        details={"name": product.name},
        ip_address=ip, user_agent=ua,
    )
    return product


@router.post("/{product_id}/refresh-preview", response_model=RefreshPreviewResponse)
async def refresh_preview(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await product_service.get_by_id(db, product_id)
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

    images_updated = False
    main_image = amazon_data.images[0] if amazon_data.images else None
    gallery = amazon_data.images[1:] if len(amazon_data.images) > 1 else []

    try:
        paths = await download_and_store_product_images(
            product.id, main_image, gallery, settings.upload_dir, product.name,
        )
        product.image_url = paths.main_image
        product.image_gallery = paths.gallery
        images_updated = True
        await db.flush()
    except Exception:
        logger.exception("Image download failed for product %s", product.id)

    if amazon_data.variants:
        variant_asins = [v.asin for v in amazon_data.variants if v.price_cents == 0]
        if variant_asins:
            try:
                prices = await client.get_variant_prices(variant_asins)
                for v in amazon_data.variants:
                    if v.asin in prices:
                        v.price_cents = prices[v.asin]
            except Exception:
                logger.exception("Failed to fetch variant prices")

    diffs: list[ProductFieldDiff] = []
    for field, label in REFRESHABLE_FIELDS.items():
        if field == "variants":
            new_variants = [v.model_dump() for v in amazon_data.variants] if amazon_data.variants else None
            old_variants = product.variants
            if new_variants and new_variants != old_variants:
                diffs.append(ProductFieldDiff(
                    field=field, label=label,
                    old_value=old_variants, new_value=new_variants,
                ))
            continue
        old_value = getattr(product, field)
        new_value = getattr(amazon_data, field, None)
        if new_value is not None and old_value != new_value:
            diffs.append(ProductFieldDiff(
                field=field, label=label,
                old_value=old_value, new_value=new_value,
            ))

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.refresh_previewed",
        resource_type="product", resource_id=product.id,
        details={"product_name": product.name, "diff_fields": [d.field for d in diffs], "images_updated": images_updated},
        ip_address=ip, user_agent=ua,
    )

    return RefreshPreviewResponse(
        product_id=product.id,
        images_updated=images_updated,
        image_url=product.image_url,
        image_gallery=product.image_gallery,
        diffs=diffs,
    )


@router.post("/{product_id}/refresh-apply", response_model=ProductResponse)
async def refresh_apply(
    product_id: UUID,
    body: RefreshApplyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product = await product_service.get_by_id(db, product_id)

    unknown = [f for f in body.fields if f not in REFRESHABLE_FIELDS]
    if unknown:
        raise BadRequestError(f"Unknown fields: {', '.join(unknown)}")

    changes: dict[str, dict] = {}
    for field in body.fields:
        if field not in body.values:
            continue
        old_value = getattr(product, field)
        new_value = body.values[field]
        setattr(product, field, new_value)
        changes[field] = {"old": old_value, "new": new_value}

    if "variants" in changes and product.variants:
        variant_prices = [v.get("price_cents", 0) for v in product.variants if v.get("price_cents", 0) > 0]
        if variant_prices:
            product.price_min_cents = min(variant_prices)
            product.price_max_cents = max(variant_prices)

    if "brand" in changes and product.brand:
        product.brand_id = await product_service.resolve_brand_id(db, product.brand)

    await db.flush()

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.refresh_applied",
        resource_type="product", resource_id=product.id,
        details={"product_name": product.name, "changes": changes},
        ip_address=ip, user_agent=ua,
    )

    await db.refresh(product)
    return product
