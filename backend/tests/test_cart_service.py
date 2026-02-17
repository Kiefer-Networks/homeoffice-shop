"""Tests for cart service with price-change detection."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.core.exceptions import BadRequestError
from src.services.cart_service import add_to_cart, get_cart, remove_from_cart, update_cart_item
from tests.conftest import make_cart_item, make_product, make_user


class TestGetCart:
    @pytest.mark.asyncio
    @patch("src.services.cart_service.get_available_budget_cents", new_callable=AsyncMock)
    async def test_empty_cart(self, mock_budget, mock_db):
        mock_budget.return_value = 75000
        result = MagicMock()
        result.all.return_value = []
        mock_db.execute.return_value = result

        cart = await get_cart(mock_db, uuid.uuid4())
        assert cart["items"] == []
        assert cart["total_current_cents"] == 0
        assert cart["has_price_changes"] is False
        assert cart["has_unavailable_items"] is False

    @pytest.mark.asyncio
    @patch("src.services.cart_service.get_available_budget_cents", new_callable=AsyncMock)
    async def test_price_change_detection(self, mock_budget, mock_db):
        mock_budget.return_value = 75000
        user_id = uuid.uuid4()
        product = make_product(price_cents=40000)  # current price changed
        cart_item = make_cart_item(
            user_id=user_id, product_id=product.id,
            price_at_add_cents=35000,  # was 350 when added
        )

        result = MagicMock()
        result.all.return_value = [(cart_item, product)]
        mock_db.execute.return_value = result

        cart = await get_cart(mock_db, user_id)
        assert cart["has_price_changes"] is True
        assert cart["items"][0]["price_changed"] is True
        assert cart["items"][0]["price_diff_cents"] == 5000
        assert cart["total_at_add_cents"] == 35000
        assert cart["total_current_cents"] == 40000

    @pytest.mark.asyncio
    @patch("src.services.cart_service.get_available_budget_cents", new_callable=AsyncMock)
    async def test_no_price_change(self, mock_budget, mock_db):
        mock_budget.return_value = 75000
        user_id = uuid.uuid4()
        product = make_product(price_cents=35000)
        cart_item = make_cart_item(
            user_id=user_id, product_id=product.id,
            price_at_add_cents=35000,
        )

        result = MagicMock()
        result.all.return_value = [(cart_item, product)]
        mock_db.execute.return_value = result

        cart = await get_cart(mock_db, user_id)
        assert cart["has_price_changes"] is False
        assert cart["items"][0]["price_changed"] is False
        assert cart["items"][0]["price_diff_cents"] == 0

    @pytest.mark.asyncio
    @patch("src.services.cart_service.get_available_budget_cents", new_callable=AsyncMock)
    async def test_unavailable_item_detected(self, mock_budget, mock_db):
        mock_budget.return_value = 75000
        user_id = uuid.uuid4()
        product = make_product(price_cents=35000, is_active=False)
        cart_item = make_cart_item(
            user_id=user_id, product_id=product.id,
            price_at_add_cents=35000,
        )

        result = MagicMock()
        result.all.return_value = [(cart_item, product)]
        mock_db.execute.return_value = result

        cart = await get_cart(mock_db, user_id)
        assert cart["has_unavailable_items"] is True
        assert cart["items"][0]["product_active"] is False

    @pytest.mark.asyncio
    @patch("src.services.cart_service.get_available_budget_cents", new_callable=AsyncMock)
    async def test_budget_exceeded(self, mock_budget, mock_db):
        mock_budget.return_value = 20000  # only 200 EUR budget
        user_id = uuid.uuid4()
        product = make_product(price_cents=35000)  # 350 EUR product
        cart_item = make_cart_item(
            user_id=user_id, product_id=product.id,
            price_at_add_cents=35000,
        )

        result = MagicMock()
        result.all.return_value = [(cart_item, product)]
        mock_db.execute.return_value = result

        cart = await get_cart(mock_db, user_id)
        assert cart["budget_exceeded"] is True
        assert cart["available_budget_cents"] == 20000

    @pytest.mark.asyncio
    @patch("src.services.cart_service.get_available_budget_cents", new_callable=AsyncMock)
    async def test_multiple_items_total(self, mock_budget, mock_db):
        mock_budget.return_value = 100000
        user_id = uuid.uuid4()
        p1 = make_product(price_cents=20000)
        p2 = make_product(price_cents=30000)
        c1 = make_cart_item(user_id=user_id, product_id=p1.id, price_at_add_cents=20000, quantity=2)
        c2 = make_cart_item(user_id=user_id, product_id=p2.id, price_at_add_cents=30000)

        result = MagicMock()
        result.all.return_value = [(c1, p1), (c2, p2)]
        mock_db.execute.return_value = result

        cart = await get_cart(mock_db, user_id)
        assert cart["total_current_cents"] == 70000  # 2*20000 + 30000


class TestAddToCart:
    @pytest.mark.asyncio
    async def test_inactive_product_raises(self, mock_db):
        product = make_product(is_active=False)
        mock_db.get.return_value = product

        with pytest.raises(BadRequestError, match="not available"):
            await add_to_cart(mock_db, uuid.uuid4(), product.id)

    @pytest.mark.asyncio
    async def test_missing_product_raises(self, mock_db):
        mock_db.get.return_value = None

        with pytest.raises(BadRequestError, match="not available"):
            await add_to_cart(mock_db, uuid.uuid4(), uuid.uuid4())

    @pytest.mark.asyncio
    async def test_exceeds_max_quantity_raises(self, mock_db):
        product = make_product(max_quantity_per_user=1)
        mock_db.get.return_value = product
        existing = make_cart_item(
            user_id=uuid.uuid4(), product_id=product.id,
            quantity=1, price_at_add_cents=product.price_cents,
        )
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = existing_result

        with pytest.raises(BadRequestError, match="Maximum quantity"):
            await add_to_cart(mock_db, existing.user_id, product.id, quantity=1)

    @pytest.mark.asyncio
    async def test_new_item_adds_successfully(self, mock_db):
        product = make_product(max_quantity_per_user=3)
        mock_db.get.return_value = product
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = existing_result

        item = await add_to_cart(mock_db, uuid.uuid4(), product.id, quantity=1)
        assert item.quantity == 1
        assert item.price_at_add_cents == product.price_cents

    @pytest.mark.asyncio
    async def test_existing_item_increments(self, mock_db):
        product = make_product(max_quantity_per_user=5)
        mock_db.get.return_value = product
        user_id = uuid.uuid4()
        existing = make_cart_item(
            user_id=user_id, product_id=product.id,
            quantity=2, price_at_add_cents=product.price_cents,
        )
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = existing_result

        item = await add_to_cart(mock_db, user_id, product.id, quantity=2)
        assert item.quantity == 4


class TestUpdateCartItem:
    @pytest.mark.asyncio
    async def test_nonexistent_returns_none(self, mock_db):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        item = await update_cart_item(mock_db, uuid.uuid4(), uuid.uuid4(), 2)
        assert item is None

    @pytest.mark.asyncio
    async def test_zero_quantity_deletes(self, mock_db):
        user_id = uuid.uuid4()
        product_id = uuid.uuid4()
        existing = make_cart_item(user_id=user_id, product_id=product_id, quantity=1)

        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = result

        item = await update_cart_item(mock_db, user_id, product_id, 0)
        assert item is None
        mock_db.delete.assert_called_once_with(existing)

    @pytest.mark.asyncio
    async def test_exceeds_max_quantity_raises(self, mock_db):
        product = make_product(max_quantity_per_user=2)
        user_id = uuid.uuid4()
        existing = make_cart_item(user_id=user_id, product_id=product.id, quantity=1)

        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        mock_db.execute.return_value = result
        mock_db.get.return_value = product

        with pytest.raises(BadRequestError, match="Maximum quantity"):
            await update_cart_item(mock_db, user_id, product.id, 5)


class TestRemoveFromCart:
    @pytest.mark.asyncio
    async def test_remove_existing(self, mock_db):
        result = MagicMock()
        result.rowcount = 1
        mock_db.execute.return_value = result

        removed = await remove_from_cart(mock_db, uuid.uuid4(), uuid.uuid4())
        assert removed is True

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, mock_db):
        result = MagicMock()
        result.rowcount = 0
        mock_db.execute.return_value = result

        removed = await remove_from_cart(mock_db, uuid.uuid4(), uuid.uuid4())
        assert removed is False
