from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.core.exceptions import NotFoundError
from src.models.orm.user import User
from src.repositories import user_repo

router = APIRouter(prefix="/avatars", tags=["avatars"])


@router.get("/{user_id}")
async def get_avatar(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    target_user = await user_repo.get_by_id(db, user_id)
    if not target_user or not target_user.avatar_url:
        raise NotFoundError("Avatar not found")
    return RedirectResponse(url=target_user.avatar_url)
