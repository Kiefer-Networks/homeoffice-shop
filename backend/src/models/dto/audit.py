from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.models.dto.common import PaginatedResponse


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str | None = None
    action: str
    resource_type: str
    resource_id: UUID | None = None
    details: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    created_at: datetime


AuditLogListResponse = PaginatedResponse[AuditLogResponse]


class AuditFiltersResponse(BaseModel):
    actions: list[str]
    resource_types: list[str]
