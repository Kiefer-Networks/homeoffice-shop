from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


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


class UserRoleUpdate(BaseModel):
    role: str


class UserProbationOverride(BaseModel):
    probation_override: bool
