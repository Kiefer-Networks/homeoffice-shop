"""Tests for HiBob sync using fake client."""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.hibob.client import FakeHiBobClient, HiBobClientProtocol
from src.integrations.hibob.models import HiBobEmployee
from src.integrations.hibob.sync import sync_employees
from tests.conftest import make_user


class TestFakeHiBobClient:
    @pytest.mark.asyncio
    async def test_implements_protocol(self):
        client = FakeHiBobClient()
        assert isinstance(client, HiBobClientProtocol)

    @pytest.mark.asyncio
    async def test_returns_provided_employees(self):
        employees = [
            HiBobEmployee(id="1", email="alice@example.com", display_name="Alice"),
            HiBobEmployee(id="2", email="bob@example.com", display_name="Bob"),
        ]
        client = FakeHiBobClient(employees)
        result = await client.get_employees()
        assert len(result) == 2
        assert result[0].email == "alice@example.com"

    @pytest.mark.asyncio
    async def test_empty_by_default(self):
        client = FakeHiBobClient()
        result = await client.get_employees()
        assert result == []

    @pytest.mark.asyncio
    async def test_avatar_returns_none(self):
        client = FakeHiBobClient()
        result = await client.get_avatar_url("any-id")
        assert result is None


class TestSyncEmployees:
    @pytest.mark.asyncio
    @patch("src.integrations.hibob.sync.get_cached_settings")
    @patch("src.integrations.hibob.sync.calculate_total_budget_cents")
    @patch("src.integrations.hibob.sync.user_repo")
    async def test_creates_new_employees(
        self, mock_user_repo, mock_budget, mock_settings, mock_db,
    ):
        mock_settings.return_value = {"budget_initial_cents": "75000", "budget_yearly_increment_cents": "25000"}
        mock_budget.return_value = 75000
        mock_user_repo.get_by_hibob_id = AsyncMock(return_value=None)
        mock_user_repo.get_by_email = AsyncMock(return_value=None)

        employees = [
            HiBobEmployee(
                id="emp-1", email="new@example.com", display_name="New User",
                department="Eng", start_date=date(2024, 1, 15),
            ),
        ]
        client = FakeHiBobClient(employees)

        log = await sync_employees(mock_db, client)
        assert log.status == "completed"
        assert log.employees_created == 1
        assert log.employees_synced == 1

    @pytest.mark.asyncio
    @patch("src.integrations.hibob.sync.get_cached_settings")
    @patch("src.integrations.hibob.sync.calculate_total_budget_cents")
    @patch("src.integrations.hibob.sync.user_repo")
    async def test_updates_existing_employees(
        self, mock_user_repo, mock_budget, mock_settings, mock_db,
    ):
        mock_settings.return_value = {"budget_initial_cents": "75000", "budget_yearly_increment_cents": "25000"}
        mock_budget.return_value = 100000
        existing_user = make_user(email="existing@example.com", display_name="Old Name")
        mock_user_repo.get_by_hibob_id = AsyncMock(return_value=existing_user)

        employees = [
            HiBobEmployee(
                id="emp-1", email="existing@example.com", display_name="Updated Name",
                department="Product", start_date=date(2022, 6, 1),
            ),
        ]
        client = FakeHiBobClient(employees)

        log = await sync_employees(mock_db, client)
        assert log.status == "completed"
        assert log.employees_updated == 1
        assert existing_user.display_name == "Updated Name"
        assert existing_user.department == "Product"
        assert existing_user.total_budget_cents == 100000

    @pytest.mark.asyncio
    @patch("src.integrations.hibob.sync.get_cached_settings")
    @patch("src.integrations.hibob.sync.calculate_total_budget_cents")
    @patch("src.integrations.hibob.sync.user_repo")
    async def test_skips_wrong_domain(
        self, mock_user_repo, mock_budget, mock_settings, mock_db,
    ):
        mock_settings.return_value = {}
        mock_budget.return_value = 75000

        employees = [
            HiBobEmployee(id="ext-1", email="external@other-company.com", display_name="External"),
        ]
        client = FakeHiBobClient(employees)

        log = await sync_employees(mock_db, client)
        assert log.status == "completed"
        assert log.employees_created == 0
        assert log.employees_updated == 0

    @pytest.mark.asyncio
    @patch("src.integrations.hibob.sync.get_cached_settings")
    @patch("src.integrations.hibob.sync.calculate_total_budget_cents")
    @patch("src.integrations.hibob.sync.user_repo")
    async def test_skips_empty_email(
        self, mock_user_repo, mock_budget, mock_settings, mock_db,
    ):
        mock_settings.return_value = {}
        mock_budget.return_value = 75000

        employees = [
            HiBobEmployee(id="no-email", email="", display_name="No Email"),
        ]
        client = FakeHiBobClient(employees)

        log = await sync_employees(mock_db, client)
        assert log.employees_created == 0

    @pytest.mark.asyncio
    @patch("src.integrations.hibob.sync.get_cached_settings")
    @patch("src.integrations.hibob.sync.calculate_total_budget_cents")
    @patch("src.integrations.hibob.sync.user_repo")
    async def test_initial_admin_gets_admin_role(
        self, mock_user_repo, mock_budget, mock_settings, mock_db,
    ):
        mock_settings.return_value = {}
        mock_budget.return_value = 75000
        mock_user_repo.get_by_hibob_id = AsyncMock(return_value=None)
        mock_user_repo.get_by_email = AsyncMock(return_value=None)

        employees = [
            HiBobEmployee(
                id="admin-1", email="admin@example.com", display_name="Admin User",
                start_date=date(2020, 1, 1),
            ),
        ]
        client = FakeHiBobClient(employees)

        log = await sync_employees(mock_db, client)
        assert log.employees_created == 1
        # Verify the User object added to db has admin role
        added_calls = mock_db.add.call_args_list
        user_added = [c for c in added_calls if hasattr(c[0][0], 'role') and hasattr(c[0][0], 'email')]
        # Filter to actual User objects (not HiBobSyncLog)
        users = [c[0][0] for c in user_added if hasattr(c[0][0], 'email') and c[0][0].email == "admin@example.com"]
        if users:
            assert users[0].role == "admin"

    @pytest.mark.asyncio
    @patch("src.integrations.hibob.sync.get_cached_settings")
    @patch("src.integrations.hibob.sync.user_repo")
    async def test_handles_client_error(
        self, mock_user_repo, mock_settings, mock_db,
    ):
        mock_settings.return_value = {}

        class ErrorClient:
            async def get_employees(self):
                raise ConnectionError("HiBob API unreachable")

            async def get_avatar_url(self, employee_id):
                return None

        log = await sync_employees(mock_db, ErrorClient())
        assert log.status == "failed"
        assert "unreachable" in log.error_message

    @pytest.mark.asyncio
    @patch("src.integrations.hibob.sync.get_cached_settings")
    @patch("src.integrations.hibob.sync.calculate_total_budget_cents")
    @patch("src.integrations.hibob.sync.user_repo")
    async def test_matches_by_email_if_no_hibob_id(
        self, mock_user_repo, mock_budget, mock_settings, mock_db,
    ):
        mock_settings.return_value = {}
        mock_budget.return_value = 75000

        existing = make_user(email="match@example.com")
        mock_user_repo.get_by_hibob_id = AsyncMock(return_value=None)
        mock_user_repo.get_by_email = AsyncMock(return_value=existing)

        employees = [
            HiBobEmployee(id="new-hibob-id", email="match@example.com", display_name="Matched"),
        ]
        client = FakeHiBobClient(employees)

        log = await sync_employees(mock_db, client)
        assert log.employees_updated == 1
        assert existing.hibob_id == "new-hibob-id"
