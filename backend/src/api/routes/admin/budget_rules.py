from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin, require_staff
from src.api.dependencies.database import get_db
from src.audit.service import log_admin_action
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

    await log_admin_action(
        db, request, staff.id, "admin.budget_rule.created",
        resource_type="budget_rule", resource_id=rule.id,
        details={
            "effective_from": str(body.effective_from),
            "initial_cents": body.initial_cents,
            "yearly_increment_cents": body.yearly_increment_cents,
        },
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
    data = body.model_dump(exclude_unset=True)
    rule = await budget_service.update_budget_rule(db, rule_id, data)

    await log_admin_action(
        db, request, staff.id, "admin.budget_rule.updated",
        resource_type="budget_rule", resource_id=rule.id,
        details={k: (str(v) if hasattr(v, 'isoformat') else v) for k, v in data.items()},
    )
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_budget_rule(
    rule_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rule_details = await budget_service.delete_budget_rule(db, rule_id)

    await log_admin_action(
        db, request, admin.id, "admin.budget_rule.deleted",
        resource_type="budget_rule", resource_id=rule_id,
        details=rule_details,
    )
    return Response(status_code=204)
