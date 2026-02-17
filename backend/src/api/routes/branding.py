from fastapi import APIRouter

from src.services.settings_service import get_setting

router = APIRouter(tags=["branding"])


@router.get("/branding")
async def get_branding():
    return {
        "company_name": get_setting("company_name"),
    }
