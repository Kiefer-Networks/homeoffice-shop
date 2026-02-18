from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.hibob_purchase_sync_log import HiBobPurchaseSyncLog
from src.models.orm.hibob_sync_log import HiBobSyncLog


async def get_sync_logs(
    db: AsyncSession, *, page: int = 1, per_page: int = 20,
) -> tuple[list[HiBobSyncLog], int]:
    count_result = await db.execute(
        select(func.count()).select_from(HiBobSyncLog)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(HiBobSyncLog)
        .order_by(HiBobSyncLog.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(result.scalars().all()), total


async def get_purchase_sync_logs(
    db: AsyncSession, *, page: int = 1, per_page: int = 20,
) -> tuple[list[HiBobPurchaseSyncLog], int]:
    count_result = await db.execute(
        select(func.count()).select_from(HiBobPurchaseSyncLog)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(HiBobPurchaseSyncLog)
        .order_by(HiBobPurchaseSyncLog.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(result.scalars().all()), total
