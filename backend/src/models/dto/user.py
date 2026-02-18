from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    department: str | None = None
    start_date: date | None = None
    total_budget_cents: int = 0
    available_budget_cents: int = 0
    is_active: bool = True
    probation_override: bool = False
    role: str = "employee"
    avatar_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserAdminResponse(UserResponse):
    hibob_id: str | None = None
    manager_email: str | None = None
    manager_name: str | None = None
    cached_spent_cents: int = 0
    cached_adjustment_cents: int = 0
    budget_cache_updated_at: datetime | None = None
    provider: str | None = None
    last_hibob_sync: datetime | None = None
    updated_at: datetime


class UserAdminListResponse(BaseModel):
    items: list[UserAdminResponse]
    total: int
    page: int
    per_page: int


class UserSearchResult(BaseModel):
    id: UUID
    email: str
    display_name: str
    department: str | None = None
    avatar_url: str | None = None

    model_config = {"from_attributes": True}


class BudgetSummary(BaseModel):
    total_budget_cents: int
    spent_cents: int
    adjustment_cents: int
    available_cents: int


class UserDetailResponse(BaseModel):
    user: UserAdminResponse
    orders: list = []
    adjustments: list = []
    budget_summary: BudgetSummary


class UserRoleUpdate(BaseModel):
    role: Literal["employee", "admin", "manager"]


class UserProbationOverride(BaseModel):
    probation_override: bool
