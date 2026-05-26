from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai_scoring import service
from app.modules.ai_scoring.schema import CandidateResumeAnalysisRead
from app.shared.deps.organization_member import MemberContext


async def handle_get_resume_analysis(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
) -> CandidateResumeAnalysisRead:
    return await service.get_resume_analysis(db, ctx.organization.id, application_id)


async def handle_retry_resume_analysis(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
    background_tasks: BackgroundTasks,
) -> CandidateResumeAnalysisRead:
    return await service.retry_resume_analysis(
        db,
        ctx.organization.id,
        application_id,
        background_tasks,
    )
