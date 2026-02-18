import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.core.logging import setup_logging

setup_logging()

from src.api.dependencies.database import async_session_factory
from src.api.middleware.cors import setup_cors
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.request_id import RequestIdMiddleware
from src.api.middleware.security_headers import SecurityHeadersMiddleware
from src.api.routes import auth, avatars, branding, cart, categories, health, orders, products, users
from src.api.routes.admin import (
    audit as admin_audit,
    brands as admin_brands,
    budgets as admin_budgets,
    categories as admin_categories,
    hibob as admin_hibob,
    amazon as admin_amazon,
    notifications as admin_notifications,
    orders as admin_orders,
    products as admin_products,
    settings as admin_settings,
    users as admin_users,
)
from src.audit.service import ensure_audit_partitions
from src.core.config import settings
from src.services.settings_service import load_settings

logger = logging.getLogger(__name__)

try:
    settings.validate_secrets()
except ValueError as e:
    logger.critical("Secret validation failed: %s", e)
    raise SystemExit(f"FATAL: {e}") from e


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with async_session_factory() as db:
        await load_settings(db)
        try:
            await ensure_audit_partitions(db)
        except Exception:
            logger.warning("Could not ensure audit partitions at startup")
        try:
            from src.repositories import refresh_token_repo
            cleaned = await refresh_token_repo.cleanup_expired(db)
            if cleaned:
                logger.info("Cleaned up %d expired refresh tokens", cleaned)
            await db.commit()
        except Exception:
            logger.warning("Could not cleanup expired refresh tokens")
        try:
            from src.services.cart_service import cleanup_stale_items
            cleaned = await cleanup_stale_items(db)
            await db.commit()
        except Exception:
            logger.warning("Could not cleanup stale cart items")
    yield


app = FastAPI(
    title="Home Office Shop API",
    version="1.0.0",
    lifespan=lifespan,
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

setup_cors(app)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=settings.backend_url.startswith("https"),
    same_site="lax",
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)

# Public routes
app.include_router(health.router, prefix="/api")
app.include_router(branding.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(avatars.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(orders.router, prefix="/api")

# Admin routes
app.include_router(admin_products.router, prefix="/api/admin")
app.include_router(admin_brands.router, prefix="/api/admin")
app.include_router(admin_categories.router, prefix="/api/admin")
app.include_router(admin_orders.router, prefix="/api/admin")
app.include_router(admin_users.router, prefix="/api/admin")
app.include_router(admin_budgets.router, prefix="/api/admin")
app.include_router(admin_settings.router, prefix="/api/admin")
app.include_router(admin_notifications.router, prefix="/api/admin")
app.include_router(admin_audit.router, prefix="/api/admin")
app.include_router(admin_hibob.router, prefix="/api/admin")
app.include_router(admin_amazon.router, prefix="/api/admin")

# Static files for uploaded images
app.mount("/uploads", StaticFiles(directory=str(settings.upload_dir)), name="uploads")
