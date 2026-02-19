from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin, require_staff
from src.api.dependencies.database import get_db
from src.audit.service import audit_context, write_audit_log
from src.models.dto.budget import (
    BudgetRuleCreate,
    BudgetRuleResponse,
    BudgetRuleUpdate,
)
from src.models.orm.user import User
from src.services import budget_service

router = APIRouter(prefix="/budget-rules", tags=["admin-budget-rules"])


@router.get("", response_model=list[BudgetRuleResponse])
async def list_budget_rules(
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    return await budget_service.get_budget_rules(db)


@router.post("", response_model=BudgetRuleResponse, status_code=201)
async def create_budget_rule(
    body: BudgetRuleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    rule = await budget_service.create_budget_rule(
        db,
        effective_from=body.effective_from,
        initial_cents=body.initial_cents,
        yearly_increment_cents=body.yearly_increment_cents,
        created_by=staff.id,
    )

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_rule.created",
        resource_type="budget_rule", resource_id=rule.id,
        details={
            "effective_from": str(body.effective_from),
            "initial_cents": body.initial_cents,
            "yearly_increment_cents": body.yearly_increment_cents,
        },
        ip_address=ip, user_agent=ua,
    )
    return rule


@router.put("/{rule_id}", response_model=BudgetRuleResponse)
async def update_budget_rule(
    rule_id: UUID,
    body: BudgetRuleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    data = body.model_dump(exclude_none=True)
    rule = await budget_service.update_budget_rule(db, rule_id, data)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_rule.updated",
        resource_type="budget_rule", resource_id=rule.id,
        details={k: (str(v) if hasattr(v, 'isoformat') else v) for k, v in data.items()},
        ip_address=ip, user_agent=ua,
    )
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_budget_rule(
    rule_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from src.models.orm.budget import BudgetRule
    rule = await db.get(BudgetRule, rule_id)
    rule_details = {
        "effective_from": str(rule.effective_from),
        "initial_cents": rule.initial_cents,
        "yearly_increment_cents": rule.yearly_increment_cents,
    } if rule else {}

    await budget_service.delete_budget_rule(db, rule_id)

    ip, ua = audit_context(request)
    await write_audit_log(
        db, user_id=admin.id, action="admin.budget_rule.deleted",
        resource_type="budget_rule", resource_id=rule_id,
        details=rule_details,
        ip_address=ip, user_agent=ua,
    )
