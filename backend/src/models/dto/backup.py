from pydantic import BaseModel, Field


class BackupScheduleResponse(BaseModel):
    enabled: bool
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    max_backups: int = Field(ge=1, le=100)


class BackupScheduleUpdate(BaseModel):
    enabled: bool | None = None
    hour: int | None = Field(default=None, ge=0, le=23)
    minute: int | None = Field(default=None, ge=0, le=59)
    max_backups: int | None = Field(default=None, ge=1, le=100)


class BackupFileResponse(BaseModel):
    filename: str
    size_bytes: int
    created_at: str


class BackupListResponse(BaseModel):
    items: list[BackupFileResponse]
