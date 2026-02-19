import csv
import io
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from dateutil.relativedelta import relativedelta
from fastapi import Request
from sqlalchemy import String, text, func, select, and_, or_, cast
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit.models import AuditLog
from src.models.orm.user import User

logger = logging.getLogger(__name__)


def audit_context(request: Request) -> tuple[str | None, str | None]:
    """Extract client IP (proxy-aware) and User-Agent from a request.

    Returns (ip_address, user_agent).
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = None

    user_agent = request.headers.get("user-agent")
    return ip, user_agent

_PARTITION_NAME_RE = re.compile(r"^audit_log_\d{4}_\d{2}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def write_audit_log(
    db: AsyncSession,
    *,
    user_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    correlation_id: str | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id,
    )
    db.add(entry)


async def query_audit_logs(
    db: AsyncSession,
    *,
    user_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    conditions = []

    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)
    if date_from:
        conditions.append(AuditLog.created_at >= date_from)
    if date_to:
        conditions.append(AuditLog.created_at <= date_to)

    where_clause = and_(*conditions) if conditions else True

    base_stmt = (
        select(AuditLog, User.email)
        .join(User, AuditLog.user_id == User.id, isouter=True)
        .where(where_clause)
    )

    if q:
        pattern = f"%{q}%"
        base_stmt = base_stmt.where(or_(
            User.email.ilike(pattern),
            AuditLog.action.ilike(pattern),
            cast(AuditLog.ip_address, String).ilike(pattern),
            cast(AuditLog.details, String).ilike(pattern),
        ))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        base_stmt
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for audit_entry, user_email in rows:
        items.append({
            "id": audit_entry.id,
            "user_id": audit_entry.user_id,
            "user_email": user_email,
            "action": audit_entry.action,
            "resource_type": audit_entry.resource_type,
            "resource_id": audit_entry.resource_id,
            "details": audit_entry.details,
            "ip_address": str(audit_entry.ip_address) if audit_entry.ip_address else None,
            "user_agent": audit_entry.user_agent,
            "correlation_id": audit_entry.correlation_id,
            "created_at": audit_entry.created_at,
        })

    return items, total


async def get_audit_filter_options(db: AsyncSession) -> dict:
    actions_result = await db.execute(
        select(AuditLog.action).distinct().order_by(AuditLog.action)
    )
    resource_types_result = await db.execute(
        select(AuditLog.resource_type).distinct().order_by(AuditLog.resource_type)
    )
    return {
        "actions": [r[0] for r in actions_result.all() if r[0]],
        "resource_types": [r[0] for r in resource_types_result.all() if r[0]],
    }


async def export_audit_csv(
    db: AsyncSession,
    *,
    user_id: UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
) -> str:
    MAX_EXPORT_ROWS = 10000
    items, _ = await query_audit_logs(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
        q=q,
        page=1,
        per_page=MAX_EXPORT_ROWS,
    )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id", "user_id", "user_email", "action", "resource_type",
            "resource_id", "details", "ip_address", "user_agent",
            "correlation_id", "created_at",
        ],
    )
    writer.writeheader()
    for item in items:
        item["details"] = str(item["details"]) if item["details"] else ""
        writer.writerow(item)

    return output.getvalue()


AUDIT_RETENTION_MONTHS = 12


async def ensure_audit_partitions(db: AsyncSession) -> None:
    """Create partitions for current month + next 2 months.
    Drop partitions older than AUDIT_RETENTION_MONTHS.
    """
    now = datetime.now(timezone.utc)

    for i in range(3):
        month = now + relativedelta(months=i)
        next_month = month + relativedelta(months=1)
        partition_name = f"audit_log_{month.year}_{month.month:02d}"
        start = f"{month.year}-{month.month:02d}-01"
        end = f"{next_month.year}-{next_month.month:02d}-01"

        if not _PARTITION_NAME_RE.match(partition_name):
            logger.error("Invalid partition name: %s", partition_name)
            continue
        if not _DATE_RE.match(start) or not _DATE_RE.match(end):
            logger.error("Invalid date format: start=%s end=%s", start, end)
            continue

        check_sql = text(
            "SELECT 1 FROM pg_tables WHERE tablename = :name"
        )
        result = await db.execute(check_sql, {"name": partition_name})
        if result.scalar() is None:
            # partition_name and dates are validated by regex above
            create_sql = text(
                f"CREATE TABLE {partition_name} PARTITION OF audit_log "
                f"FOR VALUES FROM ('{start}') TO ('{end}')"
            )
            await db.execute(create_sql)
            logger.info("Created audit partition: %s", partition_name)

    for month_offset in range(AUDIT_RETENTION_MONTHS + 1, AUDIT_RETENTION_MONTHS + 13):
        old_month = now - relativedelta(months=month_offset)
        partition_name = f"audit_log_{old_month.year}_{old_month.month:02d}"

        if not _PARTITION_NAME_RE.match(partition_name):
            logger.error("Invalid partition name: %s", partition_name)
            continue

        check_sql = text(
            "SELECT 1 FROM pg_tables WHERE tablename = :name"
        )
        result = await db.execute(check_sql, {"name": partition_name})
        if result.scalar() is not None:
            await db.execute(text(f"DROP TABLE {partition_name}"))
            logger.info("Dropped old audit partition: %s", partition_name)

    await db.commit()
