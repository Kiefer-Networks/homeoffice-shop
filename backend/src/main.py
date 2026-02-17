from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from src.api.middleware.cors import setup_cors
from src.api.middleware.request_id import RequestIdMiddleware
from src.api.routes import health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="Home Office Shop API",
    version="1.0.0",
    lifespan=lifespan,
)

setup_cors(app)
app.add_middleware(RequestIdMiddleware)

app.include_router(health.router, prefix="/api")
