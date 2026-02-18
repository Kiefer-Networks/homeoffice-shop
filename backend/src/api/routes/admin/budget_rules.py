from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin, require_staff
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.core.exceptions import NotFoundError
from src.models.dto.budget import (
    BudgetRuleCreate,
    BudgetRuleResponse,
    BudgetRuleUpdate,
)
from src.models.orm.budget_rule import BudgetRule
from src.models.orm.user import User

router = APIRouter(prefix="/budget-rules", tags=["admin-budget-rules"])


@router.get("", response_model=list[BudgetRuleResponse])
async def list_budget_rules(
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    result = await db.execute(
        select(BudgetRule).order_by(BudgetRule.effective_from)
    )
    return list(result.scalars().all())


@router.post("", response_model=BudgetRuleResponse, status_code=201)
async def create_budget_rule(
    body: BudgetRuleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    staff: User = Depends(require_staff),
):
    rule = BudgetRule(
        effective_from=body.effective_from,
        initial_cents=body.initial_cents,
        yearly_increment_cents=body.yearly_increment_cents,
        created_by=staff.id,
    )
    db.add(rule)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_rule.created",
        resource_type="budget_rule", resource_id=rule.id,
        details={
            "effective_from": str(body.effective_from),
            "initial_cents": body.initial_cents,
            "yearly_increment_cents": body.yearly_increment_cents,
        },
        ip_address=ip,
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
    rule = await db.get(BudgetRule, rule_id)
    if not rule:
        raise NotFoundError("Budget rule not found")

    if body.effective_from is not None:
        rule.effective_from = body.effective_from
    if body.initial_cents is not None:
        rule.initial_cents = body.initial_cents
    if body.yearly_increment_cents is not None:
        rule.yearly_increment_cents = body.yearly_increment_cents
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=staff.id, action="admin.budget_rule.updated",
        resource_type="budget_rule", resource_id=rule.id,
        details=body.model_dump(exclude_none=True, mode="json"),
        ip_address=ip,
    )

    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_budget_rule(
    rule_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rule = await db.get(BudgetRule, rule_id)
    if not rule:
        raise NotFoundError("Budget rule not found")

    await db.delete(rule)
    await db.flush()

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.budget_rule.deleted",
        resource_type="budget_rule", resource_id=rule_id,
        ip_address=ip,
    )
