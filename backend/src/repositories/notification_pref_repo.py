from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.admin_notification_pref import AdminNotificationPref


async def get_by_user_id(
    db: AsyncSession, user_id: UUID
) -> AdminNotificationPref | None:
    result = await db.execute(
        select(AdminNotificationPref).where(
            AdminNotificationPref.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def get_all(db: AsyncSession) -> dict[UUID, AdminNotificationPref]:
    result = await db.execute(select(AdminNotificationPref))
    prefs = result.scalars().all()
    return {p.user_id: p for p in prefs}


async def upsert(
    db: AsyncSession,
    user_id: UUID,
    *,
    email_enabled: bool | None = None,
    email_events: list[str] | None = None,
) -> AdminNotificationPref:
    fields = {
        "email_enabled": email_enabled,
        "email_events": email_events,
    }
    pref = await get_by_user_id(db, user_id)
    if pref:
        for key, value in fields.items():
            if value is not None:
                setattr(pref, key, value)
    else:
        init_fields = {k: v for k, v in fields.items() if v is not None}
        pref = AdminNotificationPref(user_id=user_id, **init_fields)
        db.add(pref)
    await db.flush()
    return pref
