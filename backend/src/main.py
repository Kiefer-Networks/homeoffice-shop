import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path

from src.core.logging import setup_logging

setup_logging()

from src.api.dependencies.database import async_session_factory
from src.api.middleware.cors import setup_cors
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.middleware.request_id import RequestIdMiddleware
from src.api.routes import auth, avatars, cart, categories, health, orders, products, users
from src.api.routes.admin import (
    audit as admin_audit,
    budgets as admin_budgets,
    categories as admin_categories,
    hibob as admin_hibob,
    icecat as admin_icecat,
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with async_session_factory() as db:
        await load_settings(db)
        try:
            await ensure_audit_partitions(db)
        except Exception:
            logger.warning("Could not ensure audit partitions at startup")
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
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)

# Public routes
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(avatars.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(cart.router, prefix="/api")
app.include_router(orders.router, prefix="/api")

# Admin routes
app.include_router(admin_products.router, prefix="/api/admin")
app.include_router(admin_categories.router, prefix="/api/admin")
app.include_router(admin_orders.router, prefix="/api/admin")
app.include_router(admin_users.router, prefix="/api/admin")
app.include_router(admin_budgets.router, prefix="/api/admin")
app.include_router(admin_settings.router, prefix="/api/admin")
app.include_router(admin_notifications.router, prefix="/api/admin")
app.include_router(admin_audit.router, prefix="/api/admin")
app.include_router(admin_hibob.router, prefix="/api/admin")
app.include_router(admin_icecat.router, prefix="/api/admin")

# Static files for uploaded images
uploads_path = Path("/app/uploads")
if not uploads_path.exists():
    uploads_path = Path("uploads")
    uploads_path.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")
