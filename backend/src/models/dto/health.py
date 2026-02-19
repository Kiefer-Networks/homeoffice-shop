from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class HealthDetailedResponse(BaseModel):
    status: str
    version: str | None = None
    checks: dict[str, Any]
