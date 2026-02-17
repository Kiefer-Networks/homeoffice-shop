"""Tests for auth service - token issuance, rotation, replay detection."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import UnauthorizedError
from src.core.security import create_refresh_token
from src.services.auth_service import TokenPair, issue_tokens, logout, refresh_tokens
from tests.factories import make_refresh_token, make_user


class TestIssueTokens:
    @pytest.mark.asyncio
    @patch("src.services.auth_service.refresh_token_repo")
    async def test_returns_token_pair(self, mock_repo, mock_db):
        mock_repo.create = AsyncMock()
        user_id = uuid.uuid4()

        result = await issue_tokens(mock_db, user_id, "u@x.com", "employee")
        assert isinstance(result, TokenPair)
        assert result.access_token
        assert result.refresh_token
        assert result.refresh_jti

    @pytest.mark.asyncio
    @patch("src.services.auth_service.refresh_token_repo")
    async def test_stores_refresh_in_db(self, mock_repo, mock_db):
        mock_repo.create = AsyncMock()
        user_id = uuid.uuid4()

        await issue_tokens(mock_db, user_id, "u@x.com", "admin")
        mock_repo.create.assert_called_once()
        call_kwargs = mock_repo.create.call_args
        assert call_kwargs.kwargs["user_id"] == user_id
        assert call_kwargs.kwargs["jti"] is not None
        assert call_kwargs.kwargs["token_family"] is not None


class TestRefreshTokens:
    @pytest.mark.asyncio
    async def test_invalid_token_raises(self, mock_db):
        with pytest.raises(UnauthorizedError, match="Invalid refresh token"):
            await refresh_tokens(mock_db, "garbage-token")

    @pytest.mark.asyncio
    @patch("src.services.auth_service.refresh_token_repo")
    async def test_token_not_in_db_raises(self, mock_repo, mock_db):
        user_id = uuid.uuid4()
        family = str(uuid.uuid4())
        token, jti = create_refresh_token(str(user_id), family)

        mock_repo.get_by_jti = AsyncMock(return_value=None)

        with pytest.raises(UnauthorizedError, match="not found"):
            await refresh_tokens(mock_db, token)

    @pytest.mark.asyncio
    @patch("src.services.auth_service.user_repo")
    @patch("src.services.auth_service.refresh_token_repo")
    async def test_replay_detection_revokes_family(self, mock_token_repo, mock_user_repo, mock_db):
        """When a revoked token is reused, the entire token family must be revoked."""
        user_id = uuid.uuid4()
        family = str(uuid.uuid4())
        token, jti = create_refresh_token(str(user_id), family)

        stored = make_refresh_token(
            user_id=user_id, jti=jti, token_family=family,
            revoked_at=datetime.now(timezone.utc),  # already revoked
        )
        mock_token_repo.get_by_jti = AsyncMock(return_value=stored)
        mock_token_repo.revoke_family = AsyncMock()

        with pytest.raises(UnauthorizedError, match="Token reuse detected"):
            await refresh_tokens(mock_db, token)

        mock_token_repo.revoke_family.assert_called_once_with(mock_db, family)

    @pytest.mark.asyncio
    @patch("src.services.auth_service.user_repo")
    @patch("src.services.auth_service.refresh_token_repo")
    async def test_inactive_user_raises(self, mock_token_repo, mock_user_repo, mock_db):
        user_id = uuid.uuid4()
        family = str(uuid.uuid4())
        token, jti = create_refresh_token(str(user_id), family)

        stored = make_refresh_token(user_id=user_id, jti=jti, token_family=family)
        mock_token_repo.get_by_jti = AsyncMock(return_value=stored)

        inactive_user = make_user(user_id=user_id, is_active=False)
        mock_user_repo.get_by_id = AsyncMock(return_value=inactive_user)

        with pytest.raises(UnauthorizedError, match="inactive"):
            await refresh_tokens(mock_db, token)

    @pytest.mark.asyncio
    @patch("src.services.auth_service.user_repo")
    @patch("src.services.auth_service.refresh_token_repo")
    async def test_successful_rotation(self, mock_token_repo, mock_user_repo, mock_db):
        """Valid refresh should revoke old token and issue new pair in same family."""
        user_id = uuid.uuid4()
        family = str(uuid.uuid4())
        token, jti = create_refresh_token(str(user_id), family)

        stored = make_refresh_token(user_id=user_id, jti=jti, token_family=family)
        mock_token_repo.get_by_jti = AsyncMock(return_value=stored)
        mock_token_repo.revoke_by_jti = AsyncMock()
        mock_token_repo.create = AsyncMock()

        user = make_user(user_id=user_id)
        mock_user_repo.get_by_id = AsyncMock(return_value=user)

        result = await refresh_tokens(mock_db, token)
        assert isinstance(result, TokenPair)
        assert result.access_token
        assert result.refresh_token != token  # new token issued

        mock_token_repo.revoke_by_jti.assert_called_once_with(mock_db, jti)
        mock_token_repo.create.assert_called_once()


class TestLogout:
    @pytest.mark.asyncio
    @patch("src.services.auth_service.refresh_token_repo")
    async def test_revokes_all_tokens(self, mock_repo, mock_db):
        mock_repo.revoke_all_for_user = AsyncMock()
        user_id = uuid.uuid4()

        await logout(mock_db, user_id)
        mock_repo.revoke_all_for_user.assert_called_once_with(mock_db, user_id)
