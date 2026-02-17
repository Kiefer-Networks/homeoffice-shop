from uuid import UUID

from pydantic import BaseModel


class NotificationPrefUpdate(BaseModel):
    slack_enabled: bool | None = None
    slack_events: list[str] | None = None
    email_enabled: bool | None = None
    email_events: list[str] | None = None


class NotificationPrefResponse(BaseModel):
    id: UUID
    user_id: UUID
    slack_enabled: bool
    slack_events: list[str]
    email_enabled: bool
    email_events: list[str]

    model_config = {"from_attributes": True}
