"""Tests for budget calculation and service."""
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.budget_service import (
    calculate_total_budget_cents,
    check_budget_for_order,
    get_available_budget_cents,
    get_live_adjustment_cents,
    get_live_spent_cents,
    refresh_budget_cache,
)
from tests.conftest import make_user


class TestCalculateTotalBudget:
    """Pure unit tests for budget calculation logic."""

    def test_no_start_date_returns_zero(self):
        assert calculate_total_budget_cents(None, {"budget_initial_cents": "75000", "budget_yearly_increment_cents": "25000"}) == 0

    def test_future_start_date_returns_zero(self):
        future = date(2099, 1, 1)
        settings = {"budget_initial_cents": "75000", "budget_yearly_increment_cents": "25000"}
        assert calculate_total_budget_cents(future, settings) == 0

    def test_first_year_gets_initial_only(self):
        today = date.today()
        # Start date 6 months ago (less than a year)
        start = date(today.year, max(1, today.month - 6), 1) if today.month > 6 else date(today.year - 1, today.month + 6, 1)
        settings = {"budget_initial_cents": "75000", "budget_yearly_increment_cents": "25000"}
        result = calculate_total_budget_cents(start, settings)
        assert result == 75000  # initial budget only, no completed years

    def test_after_one_year(self):
        today = date.today()
        start = date(today.year - 1, today.month, today.day)
        settings = {"budget_initial_cents": "75000", "budget_yearly_increment_cents": "25000"}
        result = calculate_total_budget_cents(start, settings)
        assert result == 100000  # 75000 + 1 * 25000

    def test_after_three_years(self):
        today = date.today()
        start = date(today.year - 3, today.month, today.day)
        settings = {"budget_initial_cents": "75000", "budget_yearly_increment_cents": "25000"}
        result = calculate_total_budget_cents(start, settings)
        assert result == 150000  # 75000 + 3 * 25000

    def test_custom_settings(self):
        today = date.today()
        start = date(today.year - 2, today.month, today.day)
        settings = {"budget_initial_cents": "100000", "budget_yearly_increment_cents": "50000"}
        result = calculate_total_budget_cents(start, settings)
        assert result == 200000  # 100000 + 2 * 50000

    def test_same_day_start_counts_as_zero_years(self):
        today = date.today()
        settings = {"budget_initial_cents": "75000", "budget_yearly_increment_cents": "25000"}
        result = calculate_total_budget_cents(today, settings)
        assert result == 75000  # just the initial


class TestGetAvailableBudgetCents:
    @pytest.mark.asyncio
    async def test_returns_zero_if_no_user(self, mock_db):
        mock_db.get.return_value = None
        result = await get_available_budget_cents(mock_db, uuid.uuid4())
        assert result == 0

    @pytest.mark.asyncio
    async def test_calculates_available(self, mock_db):
        user = make_user(total_budget_cents=100000, cached_spent_cents=30000, cached_adjustment_cents=5000)
        mock_db.get.return_value = user
        result = await get_available_budget_cents(mock_db, user.id)
        assert result == 65000  # 100000 - 30000 - 5000


class TestCheckBudgetForOrder:
    @pytest.mark.asyncio
    async def test_returns_false_if_no_user(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result
        result = await check_budget_for_order(mock_db, uuid.uuid4(), 10000)
        assert result is False

    @pytest.mark.asyncio
    async def test_sufficient_budget(self, mock_db):
        user = make_user(total_budget_cents=100000)
        # First execute call: SELECT User FOR UPDATE
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        # Subsequent calls for spent and adjustments
        spent_result = MagicMock()
        spent_result.scalar.return_value = 20000
        adj_result = MagicMock()
        adj_result.scalar.return_value = 0

        mock_db.execute.side_effect = [user_result, spent_result, adj_result]
        result = await check_budget_for_order(mock_db, user.id, 50000)
        assert result is True  # 100000 - 20000 - 0 = 80000 >= 50000

    @pytest.mark.asyncio
    async def test_insufficient_budget(self, mock_db):
        user = make_user(total_budget_cents=50000)
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        spent_result = MagicMock()
        spent_result.scalar.return_value = 40000
        adj_result = MagicMock()
        adj_result.scalar.return_value = 0

        mock_db.execute.side_effect = [user_result, spent_result, adj_result]
        result = await check_budget_for_order(mock_db, user.id, 20000)
        assert result is False  # 50000 - 40000 = 10000 < 20000

    @pytest.mark.asyncio
    async def test_exact_budget_match(self, mock_db):
        user = make_user(total_budget_cents=50000)
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        spent_result = MagicMock()
        spent_result.scalar.return_value = 0
        adj_result = MagicMock()
        adj_result.scalar.return_value = 0

        mock_db.execute.side_effect = [user_result, spent_result, adj_result]
        result = await check_budget_for_order(mock_db, user.id, 50000)
        assert result is True  # exact match should pass

    @pytest.mark.asyncio
    async def test_uses_for_update_lock(self, mock_db):
        """Verify that check_budget_for_order uses SELECT FOR UPDATE for race safety."""
        user = make_user(total_budget_cents=100000)
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        spent_result = MagicMock()
        spent_result.scalar.return_value = 0
        adj_result = MagicMock()
        adj_result.scalar.return_value = 0
        mock_db.execute.side_effect = [user_result, spent_result, adj_result]

        await check_budget_for_order(mock_db, user.id, 10000)
        # The first execute call should contain with_for_update
        first_call = mock_db.execute.call_args_list[0]
        query_str = str(first_call[0][0])
        assert "FOR UPDATE" in query_str


class TestRefreshBudgetCache:
    @pytest.mark.asyncio
    async def test_updates_user_cache(self, mock_db):
        """Verify refresh recalculates and stores cached values."""
        user_id = uuid.uuid4()
        spent_result = MagicMock()
        spent_result.scalar.return_value = 25000
        adj_result = MagicMock()
        adj_result.scalar.return_value = 5000
        update_result = MagicMock()

        mock_db.execute.side_effect = [spent_result, adj_result, update_result]

        await refresh_budget_cache(mock_db, user_id)
        assert mock_db.execute.call_count == 3
