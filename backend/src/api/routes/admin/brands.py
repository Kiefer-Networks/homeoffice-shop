from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.models.dto.brand import BrandCreate, BrandResponse, BrandUpdate
from src.models.orm.user import User
from src.services import brand_service

router = APIRouter(prefix="/brands", tags=["admin-brands"])


@router.get("", response_model=list[BrandResponse])
async def list_brands(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    return await brand_service.list_all(db)


@router.post("", response_model=BrandResponse, status_code=201)
async def create_brand(
    body: BrandCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    brand = await brand_service.create(db, name=body.name)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.brand.created",
        resource_type="brand", resource_id=brand.id,
        details={"name": brand.name}, ip_address=ip,
    )
    return brand


@router.put("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: UUID,
    body: BrandUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    brand, changes = await brand_service.update(
        db, brand_id, name=body.name, logo_url=body.logo_url,
    )

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.brand.updated",
        resource_type="brand", resource_id=brand.id,
        details=changes, ip_address=ip,
    )
    return brand


@router.delete("/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_staff),
):
    name = await brand_service.delete(db, brand_id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.brand.deleted",
        resource_type="brand", resource_id=brand_id,
        details={"name": name}, ip_address=ip,
    )
    return Response(status_code=204)
