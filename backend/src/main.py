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
    backup as admin_backup,
    brands as admin_brands,
    budget_rules as admin_budget_rules,
    budgets as admin_budgets,
    categories as admin_categories,
    hibob as admin_hibob,
    amazon as admin_amazon,
    notifications as admin_notifications,
    orders as admin_orders,
    products as admin_products,
    purchase_reviews as admin_purchase_reviews,
    settings as admin_settings,
    users as admin_users,
)
from src.audit.service import ensure_audit_partitions
from src.core.config import settings
from src.services.backup_scheduler import start_backup_scheduler, stop_backup_scheduler
from src.services.delivery_scheduler import start_delivery_scheduler, stop_delivery_scheduler
from src.services.settings_service import load_settings, seed_defaults

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
        await seed_defaults(db)
        await db.commit()
        try:
            await ensure_audit_partitions(db)
        except Exception:
            logger.exception("Failed to ensure audit partitions at startup")
        try:
            from src.repositories import refresh_token_repo
            cleaned = await refresh_token_repo.cleanup_expired(db)
            if cleaned:
                logger.info("Cleaned up %d expired refresh tokens", cleaned)
            await db.commit()
        except Exception:
            logger.exception("Failed to cleanup expired refresh tokens")
        try:
            from src.services.cart_service import cleanup_stale_items
            cleaned = await cleanup_stale_items(db)
            await db.commit()
        except Exception:
            logger.exception("Failed to cleanup stale cart items")
    start_backup_scheduler()
    start_delivery_scheduler()
    yield
    stop_delivery_scheduler()
    stop_backup_scheduler()


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
app.include_router(admin_budget_rules.router, prefix="/api/admin")
app.include_router(admin_purchase_reviews.router, prefix="/api/admin")
app.include_router(admin_backup.router, prefix="/api/admin")

# Static files for uploaded product images only (invoices are served via authenticated endpoint)
_products_upload_dir = settings.upload_dir / "products"
_products_upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads/products", StaticFiles(directory=str(_products_upload_dir)), name="uploads-products")
