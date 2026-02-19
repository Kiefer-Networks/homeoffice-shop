from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class StatusResponse(BaseModel):
    status: str
    message: str | None = None


class CountResponse(BaseModel):
    count: int
