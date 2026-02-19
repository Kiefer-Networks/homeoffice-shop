from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class HealthDetailedResponse(BaseModel):
    status: str
    checks: dict[str, Any]
