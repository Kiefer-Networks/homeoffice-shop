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


async def get_all_with_hibob_id(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).where(User.hibob_id.isnot(None))
    )
    return list(result.scalars().all())


async def get_all_active(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).where(User.is_active.is_(True)).order_by(User.display_name)
    )
    return list(result.scalars().all())


async def get_active_admins(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).where(User.is_active.is_(True), User.role == "admin")
    )
    return list(result.scalars().all())


async def get_active_staff(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User).where(User.is_active.is_(True), User.role.in_(("admin", "manager")))
    )
    return list(result.scalars().all())


async def get_all(
    db: AsyncSession,
    *,
    page: int = 1,
    per_page: int = 50,
    q: str | None = None,
    department: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    sort: str = "name_asc",
) -> tuple[list[User], int]:
    from sqlalchemy import func, or_

    base = select(User)

    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        base = base.where(
            or_(User.display_name.ilike(pattern), User.email.ilike(pattern))
        )
    if department is not None:
        base = base.where(User.department == department)
    if role is not None:
        base = base.where(User.role == role)
    if is_active is not None:
        base = base.where(User.is_active == is_active)

    sort_map = {
        "name_asc": User.display_name.asc(),
        "name_desc": User.display_name.desc(),
        "department": User.department.asc(),
        "start_date": User.start_date.desc(),
        "budget": User.total_budget_cents.desc(),
    }
    order = sort_map.get(sort, User.display_name.asc())

    count_result = await db.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        base.order_by(order).offset((page - 1) * per_page).limit(per_page)
    )
    return list(result.scalars().all()), total


async def search_active(db: AsyncSession, q: str, limit: int = 20) -> list[User]:
    from sqlalchemy import or_

    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    result = await db.execute(
        select(User)
        .where(
            User.is_active.is_(True),
            or_(User.display_name.ilike(pattern), User.email.ilike(pattern)),
        )
        .order_by(User.display_name.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


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
