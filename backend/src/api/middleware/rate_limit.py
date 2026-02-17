import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SlidingWindowCounter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        requests = self._windows[key]
        self._windows[key] = [t for t in requests if t > cutoff]

        if len(self._windows[key]) >= limit:
            retry_after = int(self._windows[key][0] - cutoff) + 1
            return False, max(retry_after, 1), 0

        self._windows[key].append(now)
        remaining = limit - len(self._windows[key])
        return True, 0, remaining


_limiter = SlidingWindowCounter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        if path in ("/api/health", "/api/branding"):
            return await call_next(request)

        if path.startswith("/api/auth"):
            limit = 10
            allowed, retry_after, remaining = _limiter.is_allowed(
                f"auth:{client_ip}", limit=limit, window_seconds=300
            )
        elif path.startswith("/api/admin"):
            limit = 120
            allowed, retry_after, remaining = _limiter.is_allowed(
                f"admin:{client_ip}", limit=limit, window_seconds=60
            )
        else:
            limit = 300
            allowed, retry_after, remaining = _limiter.is_allowed(
                f"global:{client_ip}", limit=limit, window_seconds=60
            )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
