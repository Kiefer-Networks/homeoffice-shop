"""Tests for HiBob purchase sync service."""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.hibob.client import FakeHiBobClient
from src.models.orm.order import Order
from src.services.purchase_sync import (
    _find_matching_orders,
    _parse_amount_cents,
    sync_purchases,
)
from tests.factories import make_order, make_user


class TestParseAmountCents:
    def test_simple_decimal(self):
        assert _parse_amount_cents("750.00") == 75000

    def test_european_comma(self):
        assert _parse_amount_cents("750,00") == 75000

    def test_european_thousands(self):
        assert _parse_amount_cents("1.234,56") == 123456

    def test_us_thousands(self):
        assert _parse_amount_cents("1,234.56") == 123456

    def test_integer(self):
        assert _parse_amount_cents("100") == 10000

    def test_with_currency_symbol(self):
        assert _parse_amount_cents("€750.00") == 75000

    def test_with_spaces(self):
        assert _parse_amount_cents(" 750.00 ") == 75000

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _parse_amount_cents("")

    def test_small_amount(self):
        assert _parse_amount_cents("0.50") == 50

    def test_large_amount(self):
        assert _parse_amount_cents("10.000,00") == 1000000


class TestFindMatchingOrders:
    def _make_order(self, total_cents, days_ago=0, status="pending"):
        order = make_order(
            user_id=uuid.uuid4(),
            total_cents=total_cents,
            status=status,
        )
        order.created_at = datetime(
            2024, 6, max(1, 15 - days_ago), tzinfo=timezone.utc
        )
        return order

    def test_exact_match(self):
        order = self._make_order(75000)
        matches = _find_matching_orders([order], 75000, date(2024, 6, 15))
        assert len(matches) == 1

    def test_within_amount_tolerance(self):
        order = self._make_order(75050)
        matches = _find_matching_orders([order], 75000, date(2024, 6, 15))
        assert len(matches) == 1

    def test_outside_amount_tolerance(self):
        order = self._make_order(76000)
        matches = _find_matching_orders([order], 75000, date(2024, 6, 15))
        assert len(matches) == 0

    def test_within_date_tolerance(self):
        order = self._make_order(75000, days_ago=5)
        matches = _find_matching_orders([order], 75000, date(2024, 6, 15))
        assert len(matches) == 1

    def test_outside_date_tolerance(self):
        order = self._make_order(75000)
        matches = _find_matching_orders([order], 75000, date(2024, 5, 1))
        assert len(matches) == 0

    def test_skips_cancelled_orders(self):
        order = self._make_order(75000, status="cancelled")
        matches = _find_matching_orders([order], 75000, date(2024, 6, 15))
        assert len(matches) == 0

    def test_skips_rejected_orders(self):
        order = self._make_order(75000, status="rejected")
        matches = _find_matching_orders([order], 75000, date(2024, 6, 15))
        assert len(matches) == 0

    def test_multiple_matches(self):
        o1 = self._make_order(75000)
        o2 = self._make_order(75050)
        matches = _find_matching_orders([o1, o2], 75000, date(2024, 6, 15))
        assert len(matches) == 2


class TestSyncPurchases:
    @pytest.mark.asyncio
    @patch("src.services.purchase_sync.get_setting")
    @patch("src.services.purchase_sync.refresh_budget_cache")
    async def test_fails_when_table_not_configured(
        self, mock_refresh, mock_get_setting, mock_db,
    ):
        mock_get_setting.return_value = ""  # empty table_id

        client = FakeHiBobClient()
        log = await sync_purchases(mock_db, client)
        assert log.status == "failed"
        assert "not configured" in log.error_message

    @pytest.mark.asyncio
    @patch("src.services.purchase_sync.get_setting")
    @patch("src.services.purchase_sync.refresh_budget_cache")
    async def test_no_users_with_hibob_id(
        self, mock_refresh, mock_get_setting, mock_db,
    ):
        def setting_side_effect(key):
            return {
                "hibob_purchase_table_id": "purchases",
                "hibob_purchase_col_date": "date",
                "hibob_purchase_col_description": "desc",
                "hibob_purchase_col_amount": "amount",
                "hibob_purchase_col_currency": "currency",
            }.get(key, "")

        mock_get_setting.side_effect = setting_side_effect

        # Mock execute to return empty user list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        client = FakeHiBobClient()
        log = await sync_purchases(mock_db, client)
        assert log.status == "completed"
        assert log.entries_found == 0

    @pytest.mark.asyncio
    @patch("src.services.purchase_sync.get_setting")
    @patch("src.services.purchase_sync.refresh_budget_cache")
    async def test_skips_already_processed_entries(
        self, mock_refresh, mock_get_setting, mock_db,
    ):
        def setting_side_effect(key):
            return {
                "hibob_purchase_table_id": "purchases",
                "hibob_purchase_col_date": "date",
                "hibob_purchase_col_description": "desc",
                "hibob_purchase_col_amount": "amount",
                "hibob_purchase_col_currency": "currency",
            }.get(key, "")

        mock_get_setting.side_effect = setting_side_effect

        user = make_user(hibob_id="emp-1")
        user.hibob_id = "emp-1"

        # First execute returns users, second returns orders, third returns existing review
        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                # Users query
                mock_result.scalars.return_value.all.return_value = [user]
            elif call_count == 2:
                # Orders query
                mock_result.scalars.return_value.all.return_value = []
            else:
                # Check for existing review - return a UUID to simulate existing
                mock_result.scalar_one_or_none.return_value = uuid.uuid4()
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        client = FakeHiBobClient(
            custom_tables={
                ("emp-1", "purchases"): [
                    {"id": "entry-1", "date": "2024-06-15", "desc": "Monitor", "amount": "750.00", "currency": "EUR"},
                ],
            }
        )

        log = await sync_purchases(mock_db, client)
        assert log.status == "completed"
        assert log.entries_found == 0  # Skipped because already exists

    @pytest.mark.asyncio
    @patch("src.services.purchase_sync.get_setting")
    @patch("src.services.purchase_sync.refresh_budget_cache")
    async def test_auto_adjust_no_matching_order(
        self, mock_refresh, mock_get_setting, mock_db,
    ):
        def setting_side_effect(key):
            return {
                "hibob_purchase_table_id": "purchases",
                "hibob_purchase_col_date": "date",
                "hibob_purchase_col_description": "desc",
                "hibob_purchase_col_amount": "amount",
                "hibob_purchase_col_currency": "currency",
            }.get(key, "")

        mock_get_setting.side_effect = setting_side_effect

        user = make_user(hibob_id="emp-1")
        user.hibob_id = "emp-1"

        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                # Users
                mock_result.scalars.return_value.all.return_value = [user]
            elif call_count == 2:
                # Orders
                mock_result.scalars.return_value.all.return_value = []
            else:
                # Check existing review / flush
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_db.execute = AsyncMock(side_effect=execute_side_effect)

        client = FakeHiBobClient(
            custom_tables={
                ("emp-1", "purchases"): [
                    {"id": "entry-1", "date": "2024-06-15", "desc": "Monitor", "amount": "750.00", "currency": "EUR"},
                ],
            }
        )

        admin_id = uuid.uuid4()
        log = await sync_purchases(mock_db, client, triggered_by=admin_id)
        assert log.status == "completed"
        assert log.entries_found == 1
        assert log.auto_adjusted == 1
        assert log.matched == 0
        assert log.pending_review == 0

        # Verify a BudgetAdjustment was added
        add_calls = mock_db.add.call_args_list
        adjustments = [c for c in add_calls if hasattr(c[0][0], 'source') and getattr(c[0][0], 'source', None) == 'hibob']
        assert len(adjustments) >= 1
        adj = adjustments[0][0][0]
        assert adj.amount_cents == -75000
        assert adj.hibob_entry_id == "entry-1"

    @pytest.mark.asyncio
    async def test_fake_client_custom_tables(self):
        client = FakeHiBobClient(
            custom_tables={
                ("emp-1", "table-a"): [{"id": "1", "value": "test"}],
            }
        )
        result = await client.get_custom_table("emp-1", "table-a")
        assert len(result) == 1
        assert result[0]["value"] == "test"

    @pytest.mark.asyncio
    async def test_fake_client_empty_custom_tables(self):
        client = FakeHiBobClient()
        result = await client.get_custom_table("emp-1", "table-a")
        assert result == []

    @pytest.mark.asyncio
    async def test_fake_client_still_implements_protocol(self):
        from src.integrations.hibob.client import HiBobClientProtocol
        client = FakeHiBobClient()
        assert isinstance(client, HiBobClientProtocol)
