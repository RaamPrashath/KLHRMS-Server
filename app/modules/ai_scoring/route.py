from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_scoring.controller import (
    handle_get_resume_analysis,
    handle_retry_resume_analysis,
)
from app.modules.ai_scoring.schema import CandidateResumeAnalysisRead
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_any_permission, require_permission

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get(
    "/applications/{application_id}/resume-analysis",
    response_model=CandidateResumeAnalysisRead,
)
async def get_resume_analysis(
    application_id: str,
    ctx: Annotated[MemberContext, Depends(require_any_permission(("candidates", "view"), ("interviews", "view"), ("jobs", "view")))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CandidateResumeAnalysisRead:
    return await handle_get_resume_analysis(ctx, db, application_id)


@router.post(
    "/applications/{application_id}/resume-analysis/retry",
    response_model=CandidateResumeAnalysisRead,
)
async def retry_resume_analysis(
    application_id: str,
    background_tasks: BackgroundTasks,
    ctx: Annotated[MemberContext, Depends(require_any_permission(("candidates", "view"), ("interviews", "view"), ("jobs", "view")))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CandidateResumeAnalysisRead:
    return await handle_retry_resume_analysis(ctx, db, application_id, background_tasks)
