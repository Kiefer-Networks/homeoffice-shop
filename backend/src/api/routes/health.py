from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.models.dto.health import HealthDetailedResponse, HealthResponse
from src.models.orm.user import User
from src.services import health_service

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    body, status_code = await health_service.get_basic_health(db)
    return JSONResponse(content=body, status_code=status_code)


@router.get("/health/detailed", response_model=HealthDetailedResponse)
async def health_check_detailed(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await health_service.get_detailed_health(db)
