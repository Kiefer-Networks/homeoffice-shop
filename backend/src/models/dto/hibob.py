from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class HiBobSyncLogResponse(BaseModel):
    id: UUID
    status: str
    employees_synced: int = 0
    employees_created: int = 0
    employees_updated: int = 0
    employees_deactivated: int = 0
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class HiBobSyncLogListResponse(BaseModel):
    items: list[HiBobSyncLogResponse]
    total: int
    page: int
    per_page: int
