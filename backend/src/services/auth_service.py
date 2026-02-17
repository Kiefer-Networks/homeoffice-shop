import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import UnauthorizedError
from src.core.security import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from src.repositories import refresh_token_repo, user_repo


class TokenPair:
    def __init__(self, access_token: str, refresh_token: str, refresh_jti: str):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.refresh_jti = refresh_jti


async def issue_tokens(
    db: AsyncSession,
    user_id: uuid.UUID,
    email: str,
    role: str,
) -> TokenPair:
    """Issue a new token pair with a fresh token family."""
    family = str(uuid.uuid4())
    access_token = create_access_token(str(user_id), email, role)
    refresh_token, jti = create_refresh_token(str(user_id), family)

    await refresh_token_repo.create(
        db,
        user_id=user_id,
        jti=jti,
        token_family=family,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.jwt_refresh_token_expire_days),
    )

    return TokenPair(access_token, refresh_token, jti)


async def refresh_tokens(db: AsyncSession, refresh_token_str: str) -> TokenPair:
    """Rotate refresh token. Detects replay attacks via family revocation."""
    payload = verify_refresh_token(refresh_token_str)
    if not payload:
        raise UnauthorizedError("Invalid refresh token")

    jti = payload.get("jti")
    token_family = payload.get("token_family")
    user_id_str = payload.get("sub")

    if not jti or not token_family or not user_id_str:
        raise UnauthorizedError("Invalid refresh token payload")

    stored_token = await refresh_token_repo.get_by_jti(db, jti)
    if not stored_token:
        raise UnauthorizedError("Refresh token not found")

    if stored_token.revoked_at is not None:
        # Replay detected: revoke entire family
        await refresh_token_repo.revoke_family(db, token_family)
        raise UnauthorizedError("Token reuse detected, all sessions revoked")

    user_id = uuid.UUID(user_id_str)
    user = await user_repo.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    # Revoke the old token
    await refresh_token_repo.revoke_by_jti(db, jti)

    # Issue new tokens in the same family
    access_token = create_access_token(str(user.id), user.email, user.role)
    new_refresh_token, new_jti = create_refresh_token(str(user.id), token_family)

    await refresh_token_repo.create(
        db,
        user_id=user.id,
        jti=new_jti,
        token_family=token_family,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.jwt_refresh_token_expire_days),
    )

    return TokenPair(access_token, new_refresh_token, new_jti)


async def logout(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke all refresh tokens for a user."""
    await refresh_token_repo.revoke_all_for_user(db, user_id)
