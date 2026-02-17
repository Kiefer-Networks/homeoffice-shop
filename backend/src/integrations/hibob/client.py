import logging
from typing import Protocol, runtime_checkable

import httpx

from src.core.config import settings
from src.integrations.hibob.models import HiBobEmployee

logger = logging.getLogger(__name__)

HIBOB_API_BASE = "https://api.hibob.com/v1"


@runtime_checkable
class HiBobClientProtocol(Protocol):
    async def get_employees(self) -> list[HiBobEmployee]: ...
    async def get_avatar_url(self, employee_id: str) -> str | None: ...


class HiBobClient:
    def __init__(self):
        self._headers = {
            "Authorization": f"Basic {settings.hibob_api_key}",
            "Accept": "application/json",
        }

    async def get_employees(self) -> list[HiBobEmployee]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{HIBOB_API_BASE}/people/search",
                headers={**self._headers, "Content-Type": "application/json"},
                json={"showInactive": False, "humanReadable": "REPLACE"},
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "application/json" not in content_type:
                raise RuntimeError(
                    f"HiBob API returned unexpected content-type: {content_type} "
                    f"(status {resp.status_code}). Check your HIBOB_API_KEY credentials."
                )
            data = resp.json()

        employees = []
        for emp in data.get("employees", []):
            try:
                work = emp.get("work", {})
                personal = emp.get("personal", {})

                start_date = None
                raw_start = work.get("startDate")
                if raw_start:
                    from datetime import date as date_type
                    start_date = date_type.fromisoformat(raw_start)

                manager_email = None
                manager_name = None
                manager_ref = work.get("reportsTo", {})
                if isinstance(manager_ref, dict):
                    manager_email = manager_ref.get("email")
                    manager_name = manager_ref.get("displayName")

                employees.append(HiBobEmployee(
                    id=str(emp["id"]),
                    email=emp.get("email", ""),
                    display_name=f"{personal.get('firstName', '')} {personal.get('surname', '')}".strip()
                    or emp.get("displayName", emp.get("email", "")),
                    department=work.get("department"),
                    manager_email=manager_email,
                    manager_name=manager_name,
                    start_date=start_date,
                    avatar_url=emp.get("avatarUrl"),
                ))
            except Exception:
                logger.exception("Failed to parse HiBob employee: %s", emp.get("id"))

        return employees

    async def get_avatar_url(self, employee_id: str) -> str | None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{HIBOB_API_BASE}/avatars/{employee_id}",
                headers=self._headers,
            )
            if resp.status_code == 200:
                return str(resp.url)
        return None


class FakeHiBobClient:
    """Test fake returning predefined data."""

    def __init__(self, employees: list[HiBobEmployee] | None = None):
        self.employees = employees or []

    async def get_employees(self) -> list[HiBobEmployee]:
        return self.employees

    async def get_avatar_url(self, employee_id: str) -> str | None:
        return None
