from pydantic import BaseModel


class AppSettingUpdate(BaseModel):
    value: str


class AppSettingResponse(BaseModel):
    key: str
    value: str

    model_config = {"from_attributes": True}


class AppSettingsResponse(BaseModel):
    settings: dict[str, str]
