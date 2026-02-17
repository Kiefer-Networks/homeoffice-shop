from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.orm.refresh_token import RefreshToken


async def create(
    db: AsyncSession,
    *,
    user_id: UUID,
    jti: str,
    token_family: str,
    expires_at: datetime,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        jti=jti,
        token_family=token_family,
        expires_at=expires_at,
    )
    db.add(token)
    await db.flush()
    return token


async def get_by_jti(db: AsyncSession, jti: str) -> RefreshToken | None:
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    )
    return result.scalar_one_or_none()


async def revoke_by_jti(db: AsyncSession, jti: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.jti == jti)
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def revoke_family(db: AsyncSession, token_family: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_family == token_family,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def revoke_all_for_user(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def cleanup_expired(db: AsyncSession) -> int:
    result = await db.execute(
        delete(RefreshToken).where(
            RefreshToken.expires_at < datetime.now(timezone.utc)
        )
    )
    return result.rowcount
