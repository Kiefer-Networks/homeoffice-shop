import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin, require_staff
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.models.dto.product import (
    ProductCreate, ProductResponse, ProductUpdate,
    RefreshPreviewResponse, RefreshApplyRequest,
)
from src.models.orm.user import User
from src.services import product_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["admin-products"])


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
        await product_service.enrich_from_amazon(db, product, product.amazon_asin)

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


@router.patch("/{product_id}/activate", response_model=ProductResponse)
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


@router.patch("/{product_id}/deactivate", response_model=ProductResponse)
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


@router.post("/{product_id}/archive", response_model=ProductResponse)
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
    preview = await product_service.generate_refresh_preview(db, product_id)

    product = await product_service.get_by_id(db, product_id)
    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.refresh_previewed",
        resource_type="product", resource_id=product.id,
        details={"product_name": product.name, "diff_fields": [d.field for d in preview.diffs], "images_updated": preview.images_updated},
        ip_address=ip, user_agent=ua,
    )

    return preview


@router.post("/{product_id}/refresh-apply", response_model=ProductResponse)
async def refresh_apply(
    product_id: UUID,
    body: RefreshApplyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    product, changes = await product_service.apply_refresh(
        db, product_id, body.fields, body.values,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.product.refresh_applied",
        resource_type="product", resource_id=product.id,
        details={"product_name": product.name, "changes": changes},
        ip_address=ip, user_agent=ua,
    )

    return product


@router.post("/refresh-prices")
async def trigger_price_refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    result = await product_service.refresh_all_prices(db)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=user.id, action="product.price_refresh_triggered",
        resource_type="product", details=result,
        ip_address=ip, user_agent=ua,
    )
    return result
