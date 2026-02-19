from fastapi import APIRouter

from src.models.dto.common import BrandingResponse
from src.services.settings_service import get_setting

router = APIRouter(tags=["branding"])


@router.get("/branding", response_model=BrandingResponse)
async def get_branding():
    return {
        "company_name": get_setting("company_name"),
    }
