from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class BudgetAdjustmentCreate(BaseModel):
    user_id: UUID
    amount_cents: int
    reason: str


class BudgetAdjustmentResponse(BaseModel):
    id: UUID
    user_id: UUID
    amount_cents: int
    reason: str
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
