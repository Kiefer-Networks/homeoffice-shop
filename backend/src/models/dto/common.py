from pydantic import BaseModel


class CountResponse(BaseModel):
    count: int


class BrandingResponse(BaseModel):
    company_name: str
