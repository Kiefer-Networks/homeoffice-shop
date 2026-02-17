from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.database import get_db
from src.core.exceptions import ForbiddenError, UnauthorizedError
from src.core.security import verify_access_token
from src.models.orm.user import User
from src.repositories import user_repo

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise UnauthorizedError("Missing authentication token")

    payload = verify_access_token(credentials.credentials)
    if not payload:
        raise UnauthorizedError("Invalid or expired token")

    user_id = UUID(payload["sub"])
    user = await user_repo.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    request.state.user = user
    return user


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != "admin":
        raise ForbiddenError("Admin access required")
    return user
