import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SlidingWindowCounter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        requests = self._windows[key]
        self._windows[key] = [t for t in requests if t > cutoff]

        if len(self._windows[key]) >= limit:
            retry_after = int(self._windows[key][0] - cutoff) + 1
            return False, max(retry_after, 1)

        self._windows[key].append(now)
        return True, 0


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
            allowed, retry_after = _limiter.is_allowed(
                f"auth:{client_ip}", limit=10, window_seconds=300
            )
        else:
            allowed, retry_after = _limiter.is_allowed(
                f"global:{client_ip}", limit=300, window_seconds=60
            )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
