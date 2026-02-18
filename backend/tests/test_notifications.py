"""Tests for notification service - email/slack preference filtering."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.notifications.service import notify_staff_email, notify_staff_slack
from tests.factories import make_user


def make_pref(*, slack_enabled=True, slack_events=None, email_enabled=True, email_events=None):
    pref = MagicMock()
    pref.slack_enabled = slack_enabled
    pref.slack_events = slack_events or ["order.created"]
    pref.email_enabled = email_enabled
    pref.email_events = email_events or ["order.created"]
    return pref


class TestNotifyStaffEmail:
    @pytest.mark.asyncio
    @patch("src.notifications.service.send_email", new_callable=AsyncMock)
    @patch("src.notifications.service.notification_pref_repo")
    @patch("src.notifications.service.user_repo")
    async def test_sends_to_staff_with_event_enabled(
        self, mock_user_repo, mock_pref_repo, mock_send, mock_db,
    ):
        admin = make_user(role="admin", email="admin@example.com")
        mock_user_repo.get_active_staff = AsyncMock(return_value=[admin])
        pref = make_pref(email_enabled=True, email_events=["order.created"])
        mock_pref_repo.get_all = AsyncMock(return_value={admin.id: pref})

        await notify_staff_email(
            mock_db, event="order.created", subject="New Order",
            template_name="order_created.html", context={"order_id": "123"},
        )
        mock_send.assert_called_once_with(
            "admin@example.com", "New Order", "order_created.html", {"order_id": "123"},
        )

    @pytest.mark.asyncio
    @patch("src.notifications.service.send_email", new_callable=AsyncMock)
    @patch("src.notifications.service.notification_pref_repo")
    @patch("src.notifications.service.user_repo")
    async def test_skips_staff_with_email_disabled(
        self, mock_user_repo, mock_pref_repo, mock_send, mock_db,
    ):
        admin = make_user(role="admin")
        mock_user_repo.get_active_staff = AsyncMock(return_value=[admin])
        pref = make_pref(email_enabled=False)
        mock_pref_repo.get_all = AsyncMock(return_value={admin.id: pref})

        await notify_staff_email(
            mock_db, event="order.created", subject="Test",
            template_name="order_created.html", context={},
        )
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.notifications.service.send_email", new_callable=AsyncMock)
    @patch("src.notifications.service.notification_pref_repo")
    @patch("src.notifications.service.user_repo")
    async def test_skips_staff_without_matching_event(
        self, mock_user_repo, mock_pref_repo, mock_send, mock_db,
    ):
        admin = make_user(role="admin")
        mock_user_repo.get_active_staff = AsyncMock(return_value=[admin])
        pref = make_pref(email_enabled=True, email_events=["order.cancelled"])
        mock_pref_repo.get_all = AsyncMock(return_value={admin.id: pref})

        await notify_staff_email(
            mock_db, event="order.created", subject="Test",
            template_name="order_created.html", context={},
        )
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.notifications.service.send_email", new_callable=AsyncMock)
    @patch("src.notifications.service.notification_pref_repo")
    @patch("src.notifications.service.user_repo")
    async def test_sends_to_admin_and_manager(
        self, mock_user_repo, mock_pref_repo, mock_send, mock_db,
    ):
        admin = make_user(role="admin", email="admin@example.com")
        manager = make_user(role="manager", email="manager@example.com")
        mock_user_repo.get_active_staff = AsyncMock(return_value=[admin, manager])

        admin_pref = make_pref(email_enabled=True, email_events=["order.created"])
        manager_pref = make_pref(email_enabled=True, email_events=["order.created"])
        mock_pref_repo.get_all = AsyncMock(return_value={
            admin.id: admin_pref,
            manager.id: manager_pref,
        })

        await notify_staff_email(
            mock_db, event="order.created", subject="New Order",
            template_name="order_created.html", context={},
        )
        assert mock_send.call_count == 2

    @pytest.mark.asyncio
    @patch("src.notifications.service.send_email", new_callable=AsyncMock)
    @patch("src.notifications.service.notification_pref_repo")
    @patch("src.notifications.service.user_repo")
    async def test_manager_without_prefs_skips_admin_events(
        self, mock_user_repo, mock_pref_repo, mock_send, mock_db,
    ):
        admin = make_user(role="admin", email="admin@example.com")
        manager = make_user(role="manager", email="manager@example.com")
        mock_user_repo.get_active_staff = AsyncMock(return_value=[admin, manager])

        # Admin has prefs with hibob.sync, manager has no prefs row
        admin_pref = make_pref(email_enabled=True, email_events=["hibob.sync"])
        mock_pref_repo.get_all = AsyncMock(return_value={admin.id: admin_pref})

        await notify_staff_email(
            mock_db, event="hibob.sync", subject="HiBob Sync",
            template_name="hibob_sync_complete.html", context={},
        )
        # Only admin should receive, manager skipped (no prefs + admin-only event)
        mock_send.assert_called_once_with(
            "admin@example.com", "HiBob Sync", "hibob_sync_complete.html", {},
        )


class TestNotifyStaffSlack:
    @pytest.mark.asyncio
    @patch("src.notifications.service.send_slack_message", new_callable=AsyncMock)
    @patch("src.notifications.service.notification_pref_repo")
    @patch("src.notifications.service.user_repo")
    async def test_sends_when_staff_has_event_enabled(
        self, mock_user_repo, mock_pref_repo, mock_send, mock_db,
    ):
        admin = make_user(role="admin")
        mock_user_repo.get_active_staff = AsyncMock(return_value=[admin])
        pref = make_pref(slack_enabled=True, slack_events=["order.created"])
        mock_pref_repo.get_all = AsyncMock(return_value={admin.id: pref})

        await notify_staff_slack(
            mock_db, event="order.created", text="New order placed",
        )
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.notifications.service.send_slack_message", new_callable=AsyncMock)
    @patch("src.notifications.service.notification_pref_repo")
    @patch("src.notifications.service.user_repo")
    async def test_does_not_send_when_slack_disabled(
        self, mock_user_repo, mock_pref_repo, mock_send, mock_db,
    ):
        admin = make_user(role="admin")
        mock_user_repo.get_active_staff = AsyncMock(return_value=[admin])
        pref = make_pref(slack_enabled=False)
        mock_pref_repo.get_all = AsyncMock(return_value={admin.id: pref})

        await notify_staff_slack(
            mock_db, event="order.created", text="Test",
        )
        mock_send.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.notifications.service.send_slack_message", new_callable=AsyncMock)
    @patch("src.notifications.service.notification_pref_repo")
    @patch("src.notifications.service.user_repo")
    async def test_sends_by_default_when_no_prefs_exist(
        self, mock_user_repo, mock_pref_repo, mock_send, mock_db,
    ):
        admin = make_user(role="admin")
        mock_user_repo.get_active_staff = AsyncMock(return_value=[admin])
        mock_pref_repo.get_all = AsyncMock(return_value={})  # no prefs at all

        await notify_staff_slack(
            mock_db, event="order.created", text="Default send",
        )
        mock_send.assert_called_once()
