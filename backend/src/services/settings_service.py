import asyncio
import logging
import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.app_setting import AppSetting

logger = logging.getLogger(__name__)

_CACHE_TTL = 60  # seconds

DEFAULT_SETTINGS = {
    "budget_initial_cents": "75000",
    "budget_yearly_increment_cents": "25000",
    "probation_months": "6",
    "price_refresh_cooldown_minutes": "60",
    "price_refresh_rate_limit_per_minute": "10",
    "company_name": "Home Office Shop",
    "cart_stale_days": "30",
    "smtp_host": "",
    "smtp_port": "587",
    "smtp_username": "",
    "smtp_password": "",
    "smtp_use_tls": "true",
    "smtp_from_address": "noreply@your-company.com",
    "hibob_purchase_table_id": "",
    "hibob_purchase_col_date": "Effective date",
    "hibob_purchase_col_description": "Description",
    "hibob_purchase_col_amount": "Amount",
    "hibob_purchase_col_currency": "Currency",
    "backup_schedule_enabled": "false",
    "backup_schedule_hour": "2",
    "backup_schedule_minute": "0",
}

_cache: dict[str, str] = {}
_cache_lock = asyncio.Lock()
_cache_loaded_at: float = 0


async def load_settings(db: AsyncSession) -> dict[str, str]:
    global _cache, _cache_loaded_at
    result = await db.execute(select(AppSetting))
    settings = {s.key: s.value for s in result.scalars().all()}
    async with _cache_lock:
        _cache = {**DEFAULT_SETTINGS, **settings}
        _cache_loaded_at = time.monotonic()
    return _cache


def _is_cache_fresh() -> bool:
    return bool(_cache) and (time.monotonic() - _cache_loaded_at) < _CACHE_TTL


def get_cached_settings() -> dict[str, str]:
    if not _cache or not _is_cache_fresh():
        return dict(DEFAULT_SETTINGS)
    return dict(_cache)


def get_setting(key: str) -> str:
    if not _is_cache_fresh():
        return DEFAULT_SETTINGS.get(key, "")
    return _cache.get(key, DEFAULT_SETTINGS.get(key, ""))


def get_setting_int(key: str) -> int:
    return int(get_setting(key) or "0")


async def update_setting(
    db: AsyncSession, key: str, value: str, updated_by: UUID | None = None
) -> None:
    global _cache_loaded_at
    result = await db.execute(
        select(AppSetting).where(AppSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
        setting.updated_by = updated_by
    else:
        setting = AppSetting(key=key, value=value, updated_by=updated_by)
        db.add(setting)
    await db.flush()

    async with _cache_lock:
        _cache[key] = value
        _cache_loaded_at = time.monotonic()
    logger.info("Setting '%s' updated", key)


async def get_all_settings(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(AppSetting))
    settings = {s.key: s.value for s in result.scalars().all()}
    return {**DEFAULT_SETTINGS, **settings}


async def seed_defaults(db: AsyncSession) -> None:
    for key, value in DEFAULT_SETTINGS.items():
        result = await db.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        if not result.scalar_one_or_none():
            db.add(AppSetting(key=key, value=value))
    await db.flush()


_REDACTED_KEYS = {"smtp_password"}


async def get_all_settings_redacted(db: AsyncSession) -> dict[str, str]:
    """Return all settings with sensitive values replaced by '********'."""
    all_settings = await get_all_settings(db)
    for key in _REDACTED_KEYS:
        if key in all_settings and all_settings[key]:
            all_settings[key] = "********"
    return all_settings
