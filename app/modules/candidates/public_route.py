from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidates.schema import (
    FeedbackInfoResponse,
    FeedbackSubmitRequest,
    FeedbackSubmitResponse,
    PublicProposedSlotRead,
    PublicSlotListResponse,
    PublicSlotSelectResponse,
)
from app.modules.candidates.service import (
    get_candidate_slots_by_token,
    get_feedback_info_by_token,
    select_candidate_slot,
    submit_candidate_feedback,
)
from app.shared.database import get_db

router = APIRouter(prefix="/public/interviews", tags=["public-interviews"])


@router.get("/{token}/slots", response_model=PublicSlotListResponse)
async def list_candidate_slots(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicSlotListResponse:
    result = await get_candidate_slots_by_token(db, token)
    return PublicSlotListResponse(
        candidateName=result["candidateName"],
        jobTitle=result["jobTitle"],
        interviewerName=result["interviewerName"],
        candidateToken=result["candidateToken"],
        slots=[PublicProposedSlotRead(**s) for s in result["slots"]],
    )


@router.post("/{token}/slots/{slot_id}/select", response_model=PublicSlotSelectResponse)
async def select_slot(
    token: str,
    slot_id: str,
    db: AsyncSession = Depends(get_db),
) -> PublicSlotSelectResponse:
    result = await select_candidate_slot(db, token, slot_id)
    return PublicSlotSelectResponse(message=result["message"])


@router.get("/{token}/feedback", response_model=FeedbackInfoResponse)
async def get_feedback_info(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> FeedbackInfoResponse:
    return await get_feedback_info_by_token(db, token)


@router.post("/{token}/feedback", response_model=FeedbackSubmitResponse)
async def submit_feedback(
    token: str,
    body: FeedbackSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> FeedbackSubmitResponse:
    return await submit_candidate_feedback(db, token, body)
