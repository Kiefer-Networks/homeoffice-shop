"""Tests for RBAC - role-based access control dependencies."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.core.exceptions import ForbiddenError, UnauthorizedError
from src.core.security import create_access_token
from tests.factories import make_user


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_missing_credentials_raises(self):
        from src.api.dependencies.auth import get_current_user

        request = MagicMock()
        db = AsyncMock()

        with pytest.raises(UnauthorizedError, match="Missing"):
            await get_current_user(request, credentials=None, db=db)

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self):
        from src.api.dependencies.auth import get_current_user

        request = MagicMock()
        db = AsyncMock()
        creds = MagicMock()
        creds.credentials = "invalid.jwt.token"

        with pytest.raises(UnauthorizedError, match="Invalid"):
            await get_current_user(request, credentials=creds, db=db)

    @pytest.mark.asyncio
    @patch("src.api.dependencies.auth.user_repo")
    async def test_inactive_user_raises(self, mock_repo):
        from src.api.dependencies.auth import get_current_user

        user = make_user(is_active=False)
        mock_repo.get_by_id = AsyncMock(return_value=user)

        request = MagicMock()
        db = AsyncMock()
        token = create_access_token(str(user.id), user.email, user.role)
        creds = MagicMock()
        creds.credentials = token

        with pytest.raises(UnauthorizedError, match="inactive"):
            await get_current_user(request, credentials=creds, db=db)

    @pytest.mark.asyncio
    @patch("src.api.dependencies.auth.user_repo")
    async def test_user_not_found_raises(self, mock_repo):
        from src.api.dependencies.auth import get_current_user

        mock_repo.get_by_id = AsyncMock(return_value=None)

        user_id = uuid.uuid4()
        request = MagicMock()
        db = AsyncMock()
        token = create_access_token(str(user_id), "u@x.com", "employee")
        creds = MagicMock()
        creds.credentials = token

        with pytest.raises(UnauthorizedError, match="not found"):
            await get_current_user(request, credentials=creds, db=db)

    @pytest.mark.asyncio
    @patch("src.api.dependencies.auth.user_repo")
    async def test_valid_user_returned(self, mock_repo):
        from src.api.dependencies.auth import get_current_user

        user = make_user()
        mock_repo.get_by_id = AsyncMock(return_value=user)

        request = MagicMock()
        request.state = MagicMock()
        db = AsyncMock()
        token = create_access_token(str(user.id), user.email, user.role)
        creds = MagicMock()
        creds.credentials = token

        result = await get_current_user(request, credentials=creds, db=db)
        assert result.id == user.id
        assert result.email == user.email

    @pytest.mark.asyncio
    @patch("src.api.dependencies.auth.user_repo")
    async def test_sets_request_state(self, mock_repo):
        from src.api.dependencies.auth import get_current_user

        user = make_user()
        mock_repo.get_by_id = AsyncMock(return_value=user)

        request = MagicMock()
        request.state = MagicMock()
        db = AsyncMock()
        token = create_access_token(str(user.id), user.email, user.role)
        creds = MagicMock()
        creds.credentials = token

        await get_current_user(request, credentials=creds, db=db)
        assert request.state.user == user


class TestRequireStaff:
    @pytest.mark.asyncio
    async def test_employee_raises(self):
        from src.api.dependencies.auth import require_staff

        user = make_user(role="employee")
        with pytest.raises(ForbiddenError, match="Staff"):
            await require_staff(user=user)

    @pytest.mark.asyncio
    async def test_manager_allowed(self):
        from src.api.dependencies.auth import require_staff

        user = make_user(role="manager")
        result = await require_staff(user=user)
        assert result.role == "manager"

    @pytest.mark.asyncio
    async def test_admin_allowed(self):
        from src.api.dependencies.auth import require_staff

        user = make_user(role="admin")
        result = await require_staff(user=user)
        assert result.role == "admin"


class TestRequireAdmin:
    @pytest.mark.asyncio
    async def test_non_admin_raises(self):
        from src.api.dependencies.auth import require_admin

        user = make_user(role="employee")
        with pytest.raises(ForbiddenError, match="Admin"):
            await require_admin(user=user)

    @pytest.mark.asyncio
    async def test_admin_allowed(self):
        from src.api.dependencies.auth import require_admin

        user = make_user(role="admin")
        result = await require_admin(user=user)
        assert result.role == "admin"
