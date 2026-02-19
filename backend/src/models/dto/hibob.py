from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from src.models.dto.common import PaginatedResponse


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


HiBobSyncLogListResponse = PaginatedResponse[HiBobSyncLogResponse]


# Purchase Sync Log
class HiBobPurchaseSyncLogResponse(BaseModel):
    id: UUID
    status: str
    entries_found: int = 0
    matched: int = 0
    auto_adjusted: int = 0
    pending_review: int = 0
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


HiBobPurchaseSyncLogListResponse = PaginatedResponse[HiBobPurchaseSyncLogResponse]


# Purchase Reviews
class HiBobPurchaseReviewResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_display_name: str | None = None
    hibob_employee_id: str
    hibob_entry_id: str
    entry_date: date
    description: str
    amount_cents: int
    currency: str = "EUR"
    status: Literal["pending", "matched", "adjusted", "dismissed"] = "pending"
    matched_order_id: UUID | None = None
    adjustment_id: UUID | None = None
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


HiBobPurchaseReviewListResponse = PaginatedResponse[HiBobPurchaseReviewResponse]


class HiBobPurchaseSyncStatusResponse(BaseModel):
    running: bool


class HiBobPurchaseReviewMatchRequest(BaseModel):
    order_id: UUID
