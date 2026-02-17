from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.factories import make_user, make_product, make_cart_item, make_order, make_refresh_token  # noqa: F401


# ── Patch settings before any other import ──────────────────────────────────
@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-must-be-32-chars")
    monkeypatch.setenv("ALLOWED_EMAIL_DOMAINS", "example.com,test.com")
    monkeypatch.setenv("INITIAL_ADMIN_EMAILS", "admin@example.com")
    from src.core.config import settings
    monkeypatch.setattr(settings, "jwt_secret_key", "test-secret-key-for-unit-tests-must-be-32-chars")
    monkeypatch.setattr(settings, "jwt_access_token_expire_minutes", 15)
    monkeypatch.setattr(settings, "jwt_refresh_token_expire_days", 7)
    monkeypatch.setattr(settings, "allowed_email_domains", "example.com,test.com")
    monkeypatch.setattr(settings, "initial_admin_emails", "admin@example.com")


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db
