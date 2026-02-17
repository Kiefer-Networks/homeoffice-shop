from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.integrations.icecat.client import IcecatClient
from src.models.dto.product import IcecatLookupRequest, IcecatLookupResponse
from src.models.orm.user import User

router = APIRouter(prefix="/icecat", tags=["admin-icecat"])


@router.post("/lookup", response_model=IcecatLookupResponse)
async def lookup_product(
    body: IcecatLookupRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    client = IcecatClient()
    result = await client.lookup_by_gtin(body.gtin)

    if not result:
        return IcecatLookupResponse()

    return IcecatLookupResponse(
        name=result.title,
        description=result.description,
        brand=result.brand,
        model=result.model,
        main_image_url=result.main_image_url,
        gallery_urls=result.gallery_urls,
        specifications=result.specifications,
        price_cents=result.price_cents,
    )
