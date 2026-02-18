from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BudgetAdjustmentCreate(BaseModel):
    user_id: UUID
    amount_cents: int = Field(ge=-10_000_00, le=10_000_00)
    reason: str = Field(min_length=1, max_length=500)


class BudgetAdjustmentUpdate(BaseModel):
    amount_cents: int = Field(ge=-10_000_00, le=10_000_00)
    reason: str = Field(min_length=1, max_length=500)


class BudgetAdjustmentResponse(BaseModel):
    id: UUID
    user_id: UUID
    amount_cents: int
    reason: str
    created_by: UUID
    created_at: datetime
    user_display_name: str | None = None
    creator_display_name: str | None = None

    model_config = {"from_attributes": True}
