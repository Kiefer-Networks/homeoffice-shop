import logging
from datetime import datetime, timezone
from email.utils import parseaddr

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.hibob.client import HiBobClientProtocol
from src.models.orm.hibob_sync_log import HiBobSyncLog
from src.models.orm.user import User
from src.repositories import user_repo
from src.services.budget_service import calculate_total_budget_cents
from src.services.settings_service import get_cached_settings

logger = logging.getLogger(__name__)


async def sync_employees(
    db: AsyncSession,
    client: HiBobClientProtocol,
) -> HiBobSyncLog:
    log = HiBobSyncLog(status="running")
    db.add(log)
    await db.flush()

    try:
        employees = await client.get_employees()
        created = 0
        updated = 0
        deactivated = 0

        hibob_ids = set()
        app_settings = get_cached_settings()

        for emp in employees:
            if not emp.email:
                continue

            _, parsed_email = parseaddr(emp.email)
            domain = parsed_email.rsplit("@", 1)[-1] if "@" in parsed_email else ""
            if domain not in settings.allowed_domains_list:
                continue

            hibob_ids.add(emp.id)
            existing = await user_repo.get_by_hibob_id(db, emp.id)

            if not existing:
                existing = await user_repo.get_by_email(db, emp.email)

            budget = calculate_total_budget_cents(emp.start_date, app_settings)

            if existing:
                existing.hibob_id = emp.id
                existing.display_name = emp.display_name
                existing.department = emp.department
                existing.manager_email = emp.manager_email
                existing.manager_name = emp.manager_name
                existing.start_date = emp.start_date
                existing.total_budget_cents = budget
                existing.avatar_url = emp.avatar_url
                existing.is_active = True
                existing.last_hibob_sync = datetime.now(timezone.utc)
                updated += 1
            else:
                role = "employee"
                if emp.email in settings.initial_admin_emails_list:
                    role = "admin"

                new_user = User(
                    email=emp.email,
                    display_name=emp.display_name,
                    hibob_id=emp.id,
                    department=emp.department,
                    manager_email=emp.manager_email,
                    manager_name=emp.manager_name,
                    start_date=emp.start_date,
                    total_budget_cents=budget,
                    avatar_url=emp.avatar_url,
                    role=role,
                    last_hibob_sync=datetime.now(timezone.utc),
                )
                db.add(new_user)
                created += 1

        await db.flush()

        # Deactivate users not present in HiBob response
        if hibob_ids:
            all_hibob_users = await user_repo.get_all_with_hibob_id(db)
            for user in all_hibob_users:
                if user.hibob_id not in hibob_ids and user.is_active:
                    user.is_active = False
                    deactivated += 1

            if deactivated > 0:
                await db.flush()

        log.status = "completed"
        log.employees_synced = len(employees)
        log.employees_created = created
        log.employees_updated = updated
        log.employees_deactivated = deactivated
        log.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.now(timezone.utc)
        logger.exception("HiBob sync failed")

    await db.flush()
    return log
