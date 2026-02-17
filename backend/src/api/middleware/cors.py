import logging
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings

logger = logging.getLogger(__name__)


def _validate_origins(origins: list[str]) -> None:
    for origin in origins:
        parsed = urlparse(origin)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid CORS origin: {origin!r}")
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"CORS origin must use http or https: {origin!r}")


def setup_cors(app: FastAPI) -> None:
    _validate_origins(settings.cors_origins_list)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
        max_age=600,
    )
