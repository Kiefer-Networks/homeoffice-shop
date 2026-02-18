import uuid
from datetime import date, datetime, timedelta, timezone

from src.models.orm.user import User
from src.models.orm.product import Product
from src.models.orm.cart_item import CartItem
from src.models.orm.order import Order
from src.models.orm.refresh_token import RefreshToken


def make_user(
    *,
    user_id=None,
    email="user@example.com",
    display_name="Test User",
    role="employee",
    is_active=True,
    probation_override=False,
    start_date=None,
    total_budget_cents=75000,
    cached_spent_cents=0,
    cached_adjustment_cents=0,
    hibob_id=None,
):
    return User(
        id=user_id or uuid.uuid4(),
        email=email,
        display_name=display_name,
        role=role,
        is_active=is_active,
        probation_override=probation_override,
        start_date=start_date or date(2023, 6, 1),
        total_budget_cents=total_budget_cents,
        cached_spent_cents=cached_spent_cents,
        cached_adjustment_cents=cached_adjustment_cents,
        hibob_id=hibob_id,
        department="Engineering",
        manager_email=None,
        manager_name=None,
        avatar_url=None,
        provider=None,
        provider_id=None,
        last_hibob_sync=None,
        budget_cache_updated_at=None,
    )


def make_product(
    *,
    product_id=None,
    category_id=None,
    name="Test Monitor",
    price_cents=35000,
    is_active=True,
    max_quantity_per_user=1,
    brand="TestBrand",
):
    return Product(
        id=product_id or uuid.uuid4(),
        category_id=category_id or uuid.uuid4(),
        name=name,
        description="A test product",
        brand=brand,
        model="TM-100",
        image_url="/uploads/test.jpg",
        image_gallery=None,
        specifications=None,
        price_cents=price_cents,
        price_min_cents=None,
        price_max_cents=None,
        amazon_asin=None,
        external_url="https://example.com/product",
        is_active=is_active,
        max_quantity_per_user=max_quantity_per_user,
    )


def make_cart_item(*, user_id, product_id, quantity=1, price_at_add_cents=35000):
    return CartItem(
        id=uuid.uuid4(),
        user_id=user_id,
        product_id=product_id,
        quantity=quantity,
        price_at_add_cents=price_at_add_cents,
    )


def make_order(*, user_id, status="pending", total_cents=35000, order_id=None):
    return Order(
        id=order_id or uuid.uuid4(),
        user_id=user_id,
        status=status,
        total_cents=total_cents,
        delivery_note=None,
        admin_note=None,
        reviewed_by=None,
        reviewed_at=None,
    )


def make_refresh_token(*, user_id, jti=None, token_family=None, revoked_at=None):
    return RefreshToken(
        id=uuid.uuid4(),
        user_id=user_id,
        jti=jti or str(uuid.uuid4()),
        token_family=token_family or str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        revoked_at=revoked_at,
    )
