from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.onboarding import service
from app.modules.onboarding.schema import (
    OnboardingPublicRead,
    OnboardingSubmitDocumentsRequest,
    OnboardingSubmitDocumentsResponse,
)
from app.shared.database import get_db

router = APIRouter(prefix="/public/onboarding", tags=["public-onboarding"])


@router.get("/{token}", response_model=OnboardingPublicRead)
async def get_onboarding(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> OnboardingPublicRead:
    return await service.get_public_onboarding(db, token)


@router.post("/{token}/submit", response_model=OnboardingSubmitDocumentsResponse)
async def submit_documents(
    token: str,
    body: OnboardingSubmitDocumentsRequest,
    db: AsyncSession = Depends(get_db),
) -> OnboardingSubmitDocumentsResponse:
    return await service.submit_documents(db, token, body)
