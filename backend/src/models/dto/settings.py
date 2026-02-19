from pydantic import BaseModel, EmailStr, Field


class AppSettingUpdate(BaseModel):
    value: str = Field(max_length=10000)


class TestEmailRequest(BaseModel):
    to: EmailStr = Field(max_length=320)


class AppSettingResponse(BaseModel):
    key: str
    value: str

    model_config = {"from_attributes": True}


class AppSettingsResponse(BaseModel):
    settings: dict[str, str]
