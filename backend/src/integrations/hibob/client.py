import asyncio
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
    async def get_custom_table(self, employee_id: str, table_id: str) -> list[dict]: ...
    async def create_custom_table_entry(self, employee_id: str, table_id: str, entry: dict) -> dict: ...
    async def delete_custom_table_entry(self, employee_id: str, table_id: str, entry_id: str) -> None: ...


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

        # HiBob search API may return employees under different keys
        raw_employees = data.get("employees", [])
        if not raw_employees and isinstance(data, list):
            raw_employees = data
        logger.info(
            "HiBob API returned %d employees (response keys: %s)",
            len(raw_employees),
            list(data.keys()) if isinstance(data, dict) else type(data).__name__,
        )

        employees = []
        for emp in raw_employees:
            try:
                work = emp.get("work", {})

                start_date = None
                raw_start = work.get("startDate")
                if raw_start:
                    from datetime import date as date_type
                    try:
                        start_date = date_type.fromisoformat(raw_start)
                    except ValueError:
                        from datetime import datetime as dt_type
                        for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d"):
                            try:
                                start_date = dt_type.strptime(raw_start, fmt).date()
                                break
                            except ValueError:
                                continue

                manager_email = None
                manager_name = None
                manager_ref = work.get("reportsTo", {})
                if isinstance(manager_ref, dict):
                    manager_email = manager_ref.get("email")
                    manager_name = manager_ref.get("displayName")

                first_name = emp.get("firstName", "")
                surname = emp.get("surname", "")
                display_name = f"{first_name} {surname}".strip() or emp.get("displayName", emp.get("email", ""))

                employees.append(HiBobEmployee(
                    id=str(emp["id"]),
                    email=emp.get("email", ""),
                    display_name=display_name,
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

    async def get_custom_table(self, employee_id: str, table_id: str) -> list[dict]:
        """Fetch custom table entries for an employee. Returns [] on 403/404."""
        max_retries = 5
        for attempt in range(max_retries + 1):
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{HIBOB_API_BASE}/people/custom-tables/{employee_id}/{table_id}",
                    headers=self._headers,
                )
                if resp.status_code in (403, 404):
                    # No access or employee not found — expected, skip silently
                    return []
                if resp.status_code == 429 and attempt < max_retries:
                    wait = min(2 ** attempt, 10)  # 1s, 2s, 4s, 8s, 10s
                    logger.warning(
                        "HiBob rate limit hit for employee %s, retrying in %ds (attempt %d/%d)",
                        employee_id, wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json().get("values", [])


    async def create_custom_table_entry(self, employee_id: str, table_id: str, entry: dict) -> dict:
        """Create a new entry in an employee's custom table."""
        max_retries = 5
        for attempt in range(max_retries + 1):
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{HIBOB_API_BASE}/people/custom-tables/{employee_id}/{table_id}",
                    headers={**self._headers, "Content-Type": "application/json"},
                    json={"values": [entry]},
                )
                if resp.status_code == 429 and attempt < max_retries:
                    wait = min(2 ** attempt, 10)
                    logger.warning(
                        "HiBob rate limit hit for employee %s, retrying in %ds (attempt %d/%d)",
                        employee_id, wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    logger.error(
                        "HiBob custom table POST failed (%s): %s — payload: %s",
                        resp.status_code, resp.text, entry,
                    )
                    raise RuntimeError(
                        f"HiBob custom table POST failed ({resp.status_code})"
                    )
                return resp.json() if resp.content else {}


    async def delete_custom_table_entry(self, employee_id: str, table_id: str, entry_id: str) -> None:
        """Delete an entry from an employee's custom table."""
        max_retries = 5
        for attempt in range(max_retries + 1):
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.delete(
                    f"{HIBOB_API_BASE}/people/custom-tables/{employee_id}/{table_id}/{entry_id}",
                    headers=self._headers,
                )
                if resp.status_code == 429 and attempt < max_retries:
                    wait = min(2 ** attempt, 10)
                    logger.warning(
                        "HiBob rate limit hit for employee %s, retrying in %ds (attempt %d/%d)",
                        employee_id, wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    logger.error(
                        "HiBob custom table DELETE failed (%s): %s",
                        resp.status_code, resp.text,
                    )
                    raise RuntimeError(
                        f"HiBob custom table DELETE failed ({resp.status_code})"
                    )
                return


class FakeHiBobClient:
    """Test fake returning predefined data."""

    def __init__(
        self,
        employees: list[HiBobEmployee] | None = None,
        custom_tables: dict[tuple[str, str], list[dict]] | None = None,
    ):
        self.employees = employees or []
        self.custom_tables = custom_tables or {}

    async def get_employees(self) -> list[HiBobEmployee]:
        return self.employees

    async def get_avatar_url(self, employee_id: str) -> str | None:
        return None

    async def get_custom_table(self, employee_id: str, table_id: str) -> list[dict]:
        return self.custom_tables.get((employee_id, table_id), [])

    async def create_custom_table_entry(self, employee_id: str, table_id: str, entry: dict) -> dict:
        key = (employee_id, table_id)
        self.custom_tables.setdefault(key, []).append(entry)
        return entry

    async def delete_custom_table_entry(self, employee_id: str, table_id: str, entry_id: str) -> None:
        pass
