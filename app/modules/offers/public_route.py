from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.offers import service
from app.shared.database import get_db

router = APIRouter(prefix="/public/offers", tags=["public-offers"])


@router.get("/{token}/accept", response_class=PlainTextResponse)
async def accept_offer(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> str:
    # Product explicitly requested direct GET actions. Email security scanners may prefetch
    # these links; if false responses appear in production, move this to a confirmation page or POST.
    return await service.accept_offer_by_token(db, token)


@router.get("/{token}/reject", response_class=PlainTextResponse)
async def reject_offer(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> str:
    # Product explicitly requested direct GET actions. Email security scanners may prefetch
    # these links; if false responses appear in production, move this to a confirmation page or POST.
    return await service.reject_offer_by_token(db, token)


@router.get("/{token}/download")
async def download_offer(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    url = await service.get_offer_download_url_by_token(db, token)
    return RedirectResponse(url=url, status_code=302)
