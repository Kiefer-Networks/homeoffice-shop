import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.app_setting import AppSetting

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS = {
    "budget_initial_cents": "75000",
    "budget_yearly_increment_cents": "25000",
    "probation_months": "6",
    "price_refresh_cooldown_minutes": "60",
    "price_refresh_rate_limit_per_minute": "10",
    "company_name": "Home Office Shop",
    "cart_stale_days": "30",
}

_cache: dict[str, str] = {}
_cache_lock = asyncio.Lock()


async def load_settings(db: AsyncSession) -> dict[str, str]:
    global _cache
    result = await db.execute(select(AppSetting))
    settings = {s.key: s.value for s in result.scalars().all()}
    async with _cache_lock:
        _cache = {**DEFAULT_SETTINGS, **settings}
    return _cache


def get_cached_settings() -> dict[str, str]:
    if not _cache:
        return dict(DEFAULT_SETTINGS)
    return dict(_cache)


def get_setting(key: str) -> str:
    return _cache.get(key, DEFAULT_SETTINGS.get(key, ""))


def get_setting_int(key: str) -> int:
    return int(get_setting(key) or "0")


async def update_setting(
    db: AsyncSession, key: str, value: str, updated_by: UUID | None = None
) -> None:
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
    logger.info("Setting '%s' updated to '%s'", key, value)


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
