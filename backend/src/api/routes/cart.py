from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.models.dto import DetailResponse
from src.models.dto.cart import CartItemAdd, CartItemUpdate, CartResponse
from src.models.orm.user import User
from src.services import cart_service

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartResponse)
async def get_cart(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await cart_service.get_cart(db, user.id)


@router.post("/items", response_model=DetailResponse)
async def add_to_cart(
    body: CartItemAdd,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await cart_service.add_to_cart(
        db, user.id, body.product_id, body.quantity
    )
    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=user.id, action="cart.item_added",
        resource_type="cart_item", resource_id=item.id,
        details={"product_id": str(body.product_id), "quantity": body.quantity},
        ip_address=ip,
    )
    return {"detail": "Item added to cart"}


@router.put("/items/{product_id}", response_model=DetailResponse)
async def update_cart_item(
    product_id: UUID,
    body: CartItemUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await cart_service.update_cart_item(db, user.id, product_id, body.quantity)
    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=user.id, action="cart.item_quantity_changed",
        resource_type="cart_item",
        details={"product_id": str(product_id), "quantity": body.quantity},
        ip_address=ip,
    )
    return {"detail": "Cart item updated"}


@router.delete("/items/{product_id}", response_model=DetailResponse)
async def remove_from_cart(
    product_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    removed = await cart_service.remove_from_cart(db, user.id, product_id)
    if removed:
        ip = request.client.host if request.client else None
        await write_audit_log(
            db, user_id=user.id, action="cart.item_removed",
            resource_type="cart_item",
            details={"product_id": str(product_id)},
            ip_address=ip,
        )
    return {"detail": "Item removed from cart"}


@router.delete("", response_model=DetailResponse)
async def clear_cart(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = await cart_service.clear_cart(db, user.id)
    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=user.id, action="cart.cleared",
        resource_type="cart", details={"items_removed": count},
        ip_address=ip,
    )
    return {"detail": f"Cart cleared ({count} items removed)"}
