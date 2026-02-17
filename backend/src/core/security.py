import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

from src.core.config import settings


ALGORITHM = "HS256"


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def create_refresh_token(
    user_id: str,
    token_family: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str]:
    """Create a refresh token and return (token, jti)."""
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.jwt_refresh_token_expire_days)
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "jti": jti,
        "token_family": token_family,
        "type": "refresh",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])


def verify_access_token(token: str) -> dict | None:
    """Verify an access token and return its payload, or None if invalid."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def verify_refresh_token(token: str) -> dict | None:
    """Verify a refresh token and return its payload, or None if invalid."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
