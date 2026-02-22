from uuid import UUID

from pydantic import BaseModel


class NotificationPrefUpdate(BaseModel):
    email_enabled: bool | None = None
    email_events: list[str] | None = None


class NotificationPrefResponse(BaseModel):
    id: UUID | None = None
    user_id: UUID | None = None
    email_enabled: bool
    email_events: list[str]
    available_email_events: list[str] = []

    model_config = {"from_attributes": True}
