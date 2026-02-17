from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.user import User


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_by_hibob_id(db: AsyncSession, hibob_id: str) -> User | None:
    result = await db.execute(select(User).where(User.hibob_id == hibob_id))
    return result.scalar_one_or_none()


async def get_all_active(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).where(User.is_active == True).order_by(User.display_name)
    )
    return list(result.scalars().all())


async def get_active_admins(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).where(User.is_active == True, User.role == "admin")
    )
    return list(result.scalars().all())


async def get_all(
    db: AsyncSession, *, page: int = 1, per_page: int = 50
) -> tuple[list[User], int]:
    from sqlalchemy import func

    count_result = await db.execute(select(func.count()).select_from(User))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(User)
        .order_by(User.display_name)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(result.scalars().all()), total


async def create(db: AsyncSession, user: User) -> User:
    db.add(user)
    await db.flush()
    return user


async def update_user(db: AsyncSession, user_id: UUID, **kwargs) -> User | None:
    user = await get_by_id(db, user_id)
    if not user:
        return None
    for key, value in kwargs.items():
        setattr(user, key, value)
    await db.flush()
    return user
