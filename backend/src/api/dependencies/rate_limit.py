from fastapi import Depends, Request

from src.api.middleware.rate_limit import _limiter
from src.core.exceptions import RateLimitError


def rate_limit(limit: int = 60, window_seconds: int = 60, key_prefix: str = "endpoint"):
    """Per-endpoint rate limit dependency."""

    async def _check(request: Request):
        user = getattr(request.state, "user", None)
        if user:
            key = f"{key_prefix}:user:{user.id}"
        else:
            forwarded = request.headers.get("x-forwarded-for")
            client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
            key = f"{key_prefix}:ip:{client_ip}"

        allowed, retry_after, _remaining = _limiter.is_allowed(key, limit, window_seconds)
        if not allowed:
            raise RateLimitError(retry_after=retry_after)

    return Depends(_check)
