from datetime import date, datetime
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
    source: str = "manual"
    hibob_entry_id: str | None = None
    created_by: UUID
    created_at: datetime
    user_display_name: str | None = None
    creator_display_name: str | None = None

    model_config = {"from_attributes": True}


class BudgetAdjustmentListResponse(BaseModel):
    items: list[BudgetAdjustmentResponse]
    total: int
    page: int
    per_page: int


# Budget Rules
class BudgetRuleCreate(BaseModel):
    effective_from: date
    initial_cents: int = Field(ge=0, le=100_000_00)
    yearly_increment_cents: int = Field(ge=0, le=100_000_00)


class BudgetRuleUpdate(BaseModel):
    effective_from: date | None = None
    initial_cents: int | None = Field(default=None, ge=0, le=100_000_00)
    yearly_increment_cents: int | None = Field(default=None, ge=0, le=100_000_00)


class BudgetRuleResponse(BaseModel):
    id: UUID
    effective_from: date
    initial_cents: int
    yearly_increment_cents: int
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# User Budget Overrides
class UserBudgetOverrideCreate(BaseModel):
    effective_from: date
    effective_until: date | None = None
    initial_cents: int = Field(ge=0, le=100_000_00)
    yearly_increment_cents: int = Field(ge=0, le=100_000_00)
    reason: str = Field(min_length=1, max_length=500)


class UserBudgetOverrideUpdate(BaseModel):
    effective_from: date | None = None
    effective_until: date | None = None
    initial_cents: int | None = Field(default=None, ge=0, le=100_000_00)
    yearly_increment_cents: int | None = Field(default=None, ge=0, le=100_000_00)
    reason: str | None = Field(default=None, min_length=1, max_length=500)


class UserBudgetOverrideResponse(BaseModel):
    id: UUID
    user_id: UUID
    effective_from: date
    effective_until: date | None = None
    initial_cents: int
    yearly_increment_cents: int
    reason: str
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# Budget Timeline
class BudgetTimelineEntry(BaseModel):
    year: int
    period_from: date
    period_to: date
    amount_cents: int
    cumulative_cents: int
    source: str  # "global" or "override"
