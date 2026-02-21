import uuid
from datetime import date, datetime, timedelta, timezone

from src.integrations.amazon.models import AmazonProduct, AmazonSearchResult
from src.integrations.hibob.models import HiBobEmployee
from src.models.orm.cart_item import CartItem
from src.models.orm.order import Order
from src.models.orm.product import Product
from src.models.orm.refresh_token import RefreshToken
from src.models.orm.user import User


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


# ── Test doubles ─────────────────────────────────────────────────────────────


class FakeAmazonClient:
    """Test double for AmazonClient."""

    def __init__(self, products: dict[str, AmazonProduct] | None = None):
        self._products = products or {}

    async def search(self, query: str) -> list[AmazonSearchResult]:
        results = []
        for asin, product in self._products.items():
            if query.lower() in product.name.lower() or query == asin:
                results.append(AmazonSearchResult(
                    name=product.name,
                    asin=asin,
                    price_cents=product.price_cents,
                    image_url=product.images[0] if product.images else None,
                    url=product.url,
                ))
        return results

    async def get_product(self, asin: str) -> AmazonProduct | None:
        return self._products.get(asin)

    async def get_current_price(self, asin: str) -> int | None:
        product = self._products.get(asin)
        if product and product.price_cents > 0:
            return product.price_cents
        return None

    async def get_variant_prices(self, asins: list[str]) -> dict[str, int]:
        prices: dict[str, int] = {}
        for asin in asins:
            product = self._products.get(asin)
            if product and product.price_cents > 0:
                prices[asin] = product.price_cents
        return prices


class FakeHiBobClient:
    """Test double for HiBobClient."""

    def __init__(
        self,
        employees: list[HiBobEmployee] | None = None,
        custom_tables: dict[tuple[str, str], list[dict]] | None = None,
    ):
        self.employees = employees or []
        self.custom_tables = custom_tables or {}

    async def get_employees(self) -> list[HiBobEmployee]:
        return self.employees

    async def get_avatar_url(self, employee_id: str) -> str | None:
        return None

    async def get_custom_table(self, employee_id: str, table_id: str) -> list[dict]:
        return self.custom_tables.get((employee_id, table_id), [])

    async def create_custom_table_entry(self, employee_id: str, table_id: str, entry: dict) -> dict:
        key = (employee_id, table_id)
        self.custom_tables.setdefault(key, []).append(entry)
        return entry

    async def delete_custom_table_entry(self, employee_id: str, table_id: str, entry_id: str) -> None:
        pass
