import logging
from datetime import datetime, timezone
from email.utils import parseaddr
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.audit.service import write_audit_log
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
    admin_id: "UUID | None" = None,
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
                changed_fields = {}
                for attr, new_val in [
                    ("display_name", emp.display_name),
                    ("department", emp.department),
                    ("manager_email", emp.manager_email),
                    ("start_date", emp.start_date),
                    ("total_budget_cents", budget),
                    ("is_active", True),
                ]:
                    old_val = getattr(existing, attr)
                    if old_val != new_val:
                        changed_fields[attr] = {"old": str(old_val), "new": str(new_val)}

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

                if changed_fields:
                    await write_audit_log(
                        db,
                        user_id=admin_id or existing.id,
                        action="hibob.user.updated",
                        resource_type="user",
                        resource_id=existing.id,
                        details={
                            "email": existing.email,
                            "hibob_id": emp.id,
                            "changed_fields": changed_fields,
                            "trigger": "manual" if admin_id else "scheduled",
                        },
                    )
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
                await db.flush()
                created += 1

                await write_audit_log(
                    db,
                    user_id=admin_id or new_user.id,
                    action="hibob.user.created",
                    resource_type="user",
                    resource_id=new_user.id,
                    details={
                        "email": emp.email,
                        "display_name": emp.display_name,
                        "hibob_id": emp.id,
                        "department": emp.department,
                        "role": role,
                        "total_budget_cents": budget,
                        "trigger": "manual" if admin_id else "scheduled",
                    },
                )

        await db.flush()

        # Deactivate users not present in HiBob response
        if hibob_ids:
            all_hibob_users = await user_repo.get_all_with_hibob_id(db)
            for user in all_hibob_users:
                if user.hibob_id not in hibob_ids and user.is_active:
                    user.is_active = False
                    deactivated += 1
                    await write_audit_log(
                        db,
                        user_id=admin_id or user.id,
                        action="hibob.user.deactivated",
                        resource_type="user",
                        resource_id=user.id,
                        details={
                            "display_name": user.display_name,
                            "email": user.email,
                            "hibob_id": user.hibob_id,
                            "trigger": "manual" if admin_id else "scheduled",
                        },
                    )

            if deactivated > 0:
                await db.flush()

        log.status = "completed"
        log.employees_synced = len(employees)
        log.employees_created = created
        log.employees_updated = updated
        log.employees_deactivated = deactivated
        log.completed_at = datetime.now(timezone.utc)

        # Batch summary audit entry
        audit_user_id = admin_id
        if not audit_user_id:
            staff = await user_repo.get_active_staff(db)
            audit_user_id = staff[0].id if staff else None
        if audit_user_id:
            await write_audit_log(
                db,
                user_id=audit_user_id,
                action="hibob.sync.completed",
                resource_type="system",
                details={
                    "employees_synced": len(employees),
                    "created": created,
                    "updated": updated,
                    "deactivated": deactivated,
                    "sync_log_id": str(log.id),
                    "trigger": "manual" if admin_id else "scheduled",
                },
            )

    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)[:500]
        log.completed_at = datetime.now(timezone.utc)
        logger.exception("HiBob sync failed")

    await db.flush()
    return log
