from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.models.dto.user import UserResponse
from src.models.orm.user import User
from src.services.budget_service import get_available_budget_cents

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    available_budget = await get_available_budget_cents(db, user.id)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "department": user.department,
        "start_date": user.start_date,
        "total_budget_cents": user.total_budget_cents,
        "available_budget_cents": available_budget,
        "is_active": user.is_active,
        "probation_override": user.probation_override,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at,
    }
