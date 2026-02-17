"""Tests for settings service - caching and defaults."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.settings_service import (
    DEFAULT_SETTINGS,
    get_cached_settings,
    get_setting,
    get_setting_int,
)


class TestDefaults:
    def test_budget_initial_default(self):
        assert DEFAULT_SETTINGS["budget_initial_cents"] == "75000"

    def test_budget_increment_default(self):
        assert DEFAULT_SETTINGS["budget_yearly_increment_cents"] == "25000"

    def test_probation_months_default(self):
        assert DEFAULT_SETTINGS["probation_months"] == "6"


class TestGetCachedSettings:
    def test_returns_defaults_when_cache_empty(self):
        import src.services.settings_service as svc
        original = svc._cache.copy()
        svc._cache.clear()
        try:
            result = get_cached_settings()
            assert result["budget_initial_cents"] == "75000"
            assert result["probation_months"] == "6"
        finally:
            svc._cache.update(original)

    def test_returns_copy(self):
        result1 = get_cached_settings()
        result2 = get_cached_settings()
        assert result1 is not result2  # must be a copy


class TestGetSettingInt:
    def test_returns_integer(self):
        import src.services.settings_service as svc
        svc._cache["budget_initial_cents"] = "75000"
        assert get_setting_int("budget_initial_cents") == 75000

    def test_missing_key_returns_zero(self):
        import src.services.settings_service as svc
        svc._cache.pop("nonexistent", None)
        assert get_setting_int("nonexistent") == 0
