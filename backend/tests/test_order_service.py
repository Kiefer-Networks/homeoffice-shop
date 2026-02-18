"""Tests for order state machine and order service."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.core.exceptions import BadRequestError, ConflictError, InvalidStatusTransitionError, NotFoundError
from src.services.order_service import (
    VALID_TRANSITIONS,
    create_order_from_cart,
    transition_order,
)
from tests.factories import make_cart_item, make_order, make_product, make_user


class TestValidTransitions:
    """Pure unit tests for the state machine definition."""

    def test_pending_can_go_to_ordered(self):
        assert "ordered" in VALID_TRANSITIONS["pending"]

    def test_pending_can_go_to_rejected(self):
        assert "rejected" in VALID_TRANSITIONS["pending"]

    def test_pending_cannot_go_to_delivered(self):
        assert "delivered" not in VALID_TRANSITIONS["pending"]

    def test_pending_can_go_to_cancelled(self):
        assert "cancelled" in VALID_TRANSITIONS["pending"]

    def test_ordered_can_go_to_delivered(self):
        assert "delivered" in VALID_TRANSITIONS["ordered"]

    def test_ordered_can_go_to_cancelled(self):
        assert "cancelled" in VALID_TRANSITIONS["ordered"]

    def test_ordered_cannot_go_back_to_pending(self):
        assert "pending" not in VALID_TRANSITIONS["ordered"]

    def test_rejected_is_terminal(self):
        assert len(VALID_TRANSITIONS["rejected"]) == 0

    def test_delivered_is_terminal(self):
        assert len(VALID_TRANSITIONS["delivered"]) == 0

    def test_cancelled_is_terminal(self):
        assert len(VALID_TRANSITIONS["cancelled"]) == 0


class TestTransitionOrder:
    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        with pytest.raises(NotFoundError):
            await transition_order(mock_db, uuid.uuid4(), "ordered", uuid.uuid4())

    @pytest.mark.asyncio
    async def test_invalid_transition_raises(self, mock_db):
        user_id = uuid.uuid4()
        order = make_order(user_id=user_id, status="delivered")
        result = MagicMock()
        result.scalar_one_or_none.return_value = order
        mock_db.execute.return_value = result

        with pytest.raises(InvalidStatusTransitionError):
            await transition_order(mock_db, order.id, "pending", uuid.uuid4())

    @pytest.mark.asyncio
    @patch("src.services.order_service.refresh_budget_cache", new_callable=AsyncMock)
    async def test_valid_transition_pending_to_ordered(self, mock_refresh, mock_db):
        user_id = uuid.uuid4()
        admin_id = uuid.uuid4()
        order = make_order(user_id=user_id, status="pending")
        result = MagicMock()
        result.scalar_one_or_none.return_value = order
        mock_db.execute.return_value = result

        updated = await transition_order(mock_db, order.id, "ordered", admin_id)
        assert updated.status == "ordered"
        assert updated.reviewed_by == admin_id
        assert updated.reviewed_at is not None

    @pytest.mark.asyncio
    async def test_rejection_requires_note(self, mock_db):
        user_id = uuid.uuid4()
        order = make_order(user_id=user_id, status="pending")
        result = MagicMock()
        result.scalar_one_or_none.return_value = order
        mock_db.execute.return_value = result

        with pytest.raises(BadRequestError, match="Rejection reason"):
            await transition_order(mock_db, order.id, "rejected", uuid.uuid4())

    @pytest.mark.asyncio
    @patch("src.services.order_service.refresh_budget_cache", new_callable=AsyncMock)
    async def test_rejection_with_note_succeeds(self, mock_refresh, mock_db):
        user_id = uuid.uuid4()
        order = make_order(user_id=user_id, status="pending")
        result = MagicMock()
        result.scalar_one_or_none.return_value = order
        mock_db.execute.return_value = result

        updated = await transition_order(
            mock_db, order.id, "rejected", uuid.uuid4(),
            admin_note="Item out of stock",
        )
        assert updated.status == "rejected"
        assert updated.admin_note == "Item out of stock"

    @pytest.mark.asyncio
    @patch("src.services.order_service.refresh_budget_cache", new_callable=AsyncMock)
    async def test_ordered_to_delivered(self, mock_refresh, mock_db):
        user_id = uuid.uuid4()
        order = make_order(user_id=user_id, status="ordered")
        result = MagicMock()
        result.scalar_one_or_none.return_value = order
        mock_db.execute.return_value = result

        updated = await transition_order(mock_db, order.id, "delivered", uuid.uuid4())
        assert updated.status == "delivered"

    @pytest.mark.asyncio
    @patch("src.services.order_service.refresh_budget_cache", new_callable=AsyncMock)
    async def test_ordered_to_cancelled(self, mock_refresh, mock_db):
        user_id = uuid.uuid4()
        order = make_order(user_id=user_id, status="ordered")
        result = MagicMock()
        result.scalar_one_or_none.return_value = order
        mock_db.execute.return_value = result

        updated = await transition_order(mock_db, order.id, "cancelled", uuid.uuid4())
        assert updated.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancelled_cannot_transition(self, mock_db):
        user_id = uuid.uuid4()
        order = make_order(user_id=user_id, status="cancelled")
        result = MagicMock()
        result.scalar_one_or_none.return_value = order
        mock_db.execute.return_value = result

        with pytest.raises(InvalidStatusTransitionError):
            await transition_order(mock_db, order.id, "ordered", uuid.uuid4())


class TestCreateOrderFromCart:
    @pytest.mark.asyncio
    async def test_empty_cart_raises(self, mock_db):
        result = MagicMock()
        result.all.return_value = []
        mock_db.execute.return_value = result

        with pytest.raises(BadRequestError, match="Cart is empty"):
            await create_order_from_cart(mock_db, uuid.uuid4())

    @pytest.mark.asyncio
    async def test_unavailable_product_raises(self, mock_db):
        user_id = uuid.uuid4()
        product = make_product(is_active=False)
        cart_item = make_cart_item(user_id=user_id, product_id=product.id)

        result = MagicMock()
        result.all.return_value = [(cart_item, product)]
        mock_db.execute.return_value = result

        with pytest.raises(BadRequestError, match="no longer available"):
            await create_order_from_cart(mock_db, user_id)

    @pytest.mark.asyncio
    async def test_price_change_without_confirmation_raises(self, mock_db):
        user_id = uuid.uuid4()
        product = make_product(price_cents=40000)
        cart_item = make_cart_item(
            user_id=user_id, product_id=product.id, price_at_add_cents=35000,
        )

        result = MagicMock()
        result.all.return_value = [(cart_item, product)]
        mock_db.execute.return_value = result

        with pytest.raises(ConflictError, match="Prices have changed"):
            await create_order_from_cart(mock_db, user_id)

    @pytest.mark.asyncio
    @patch("src.services.order_service.check_budget_for_order", new_callable=AsyncMock)
    @patch("src.services.order_service.refresh_budget_cache", new_callable=AsyncMock)
    async def test_price_change_with_confirmation_succeeds(
        self, mock_refresh, mock_budget, mock_db,
    ):
        user_id = uuid.uuid4()
        product = make_product(price_cents=40000)
        cart_item = make_cart_item(
            user_id=user_id, product_id=product.id, price_at_add_cents=35000,
        )
        mock_budget.return_value = True

        cart_result = MagicMock()
        cart_result.all.return_value = [(cart_item, product)]
        delete_result = MagicMock()
        mock_db.execute.side_effect = [cart_result, delete_result]

        order = await create_order_from_cart(
            mock_db, user_id, confirm_price_changes=True,
        )
        assert order.total_cents == 40000  # uses current price
        assert order.status == "pending"

    @pytest.mark.asyncio
    @patch("src.services.order_service.check_budget_for_order", new_callable=AsyncMock)
    async def test_insufficient_budget_raises(self, mock_budget, mock_db):
        user_id = uuid.uuid4()
        product = make_product(price_cents=35000)
        cart_item = make_cart_item(
            user_id=user_id, product_id=product.id, price_at_add_cents=35000,
        )
        mock_budget.return_value = False

        result = MagicMock()
        result.all.return_value = [(cart_item, product)]
        mock_db.execute.return_value = result

        with pytest.raises(BadRequestError, match="Insufficient budget"):
            await create_order_from_cart(mock_db, user_id)
