from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.database import get_db
from src.models.orm.user import User
from src.services import user_service

router = APIRouter(prefix="/avatars", tags=["avatars"])


@router.get("/{user_id}")
async def get_avatar(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    avatar_url = await user_service.get_avatar_url(db, user_id)
    return RedirectResponse(url=avatar_url, status_code=302)
