from datetime import date

from pydantic import BaseModel


class HiBobEmployee(BaseModel):
    id: str
    email: str
    display_name: str
    department: str | None = None
    manager_email: str | None = None
    manager_name: str | None = None
    start_date: date | None = None
    avatar_url: str | None = None
    is_active: bool = True
