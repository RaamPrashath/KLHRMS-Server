from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidates import service
from app.modules.candidates.schema import (
    CandidateApplicationDetailRead,
    InterviewMeetingCreateRequest,
    InterviewMeetingRead,
    MoveApplicationStageRequest,
    PipelineApplicationRead,
    PipelineBoardRead,
    PipelineJobPostingRead,
    PipelineStageCreateRequest,
    PipelineStageRead,
    PipelineStageUpdateRequest,
    StageEvaluationWorkspaceRead,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_job_postings(
    ctx: MemberContext,
    db: AsyncSession,
) -> list[PipelineJobPostingRead]:
    return await service.list_job_postings(db, ctx.organization.id)


async def handle_get_pipeline_board(
    ctx: MemberContext,
    db: AsyncSession,
    job_posting_id: str,
) -> PipelineBoardRead:
    return await service.get_pipeline_board(db, ctx.organization.id, job_posting_id)


async def handle_move_application_stage(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
    body: MoveApplicationStageRequest,
) -> PipelineApplicationRead:
    return await service.move_application_stage(
        db,
        ctx.organization.id,
        ctx.organization.name,
        ctx.member.id,
        ctx.member.userId,
        application_id,
        body,
    )


async def handle_create_stage(
    ctx: MemberContext,
    db: AsyncSession,
    body: PipelineStageCreateRequest,
) -> PipelineStageRead:
    return await service.create_stage(
        db,
        ctx.organization.id,
        ctx.organization.name,
        ctx.member.id,
        ctx.member.userId,
        body,
    )


async def handle_update_stage(
    ctx: MemberContext,
    db: AsyncSession,
    stage_id: str,
    body: PipelineStageUpdateRequest,
) -> PipelineStageRead:
    return await service.update_stage(
        db,
        ctx.organization.id,
        ctx.organization.name,
        ctx.member.id,
        ctx.member.userId,
        stage_id,
        body,
    )


async def handle_extend_stage_due_date(
    ctx: MemberContext,
    db: AsyncSession,
    stage_id: str,
) -> PipelineStageRead:
    return await service.extend_stage_due_date(db, ctx.organization.id, stage_id)


async def handle_delete_stage(
    ctx: MemberContext,
    db: AsyncSession,
    stage_id: str,
) -> None:
    await service.delete_stage(db, ctx.organization.id, stage_id)


async def handle_get_application_detail(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
) -> CandidateApplicationDetailRead:
    return await service.get_application_detail(db, ctx.organization.id, application_id)


async def handle_create_interview_meeting(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
    body: InterviewMeetingCreateRequest,
) -> InterviewMeetingRead:
    return await service.create_interview_meeting(
        db,
        ctx.organization.id,
        ctx.member.id,
        ctx.member.userId,
        application_id,
        body,
    )


async def handle_complete_interview_meeting(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
    event_id: str,
) -> InterviewMeetingRead:
    return await service.complete_interview_meeting(
        db,
        ctx.organization.id,
        application_id,
        event_id,
    )


async def handle_get_evaluation_workspace(
    ctx: MemberContext,
    db: AsyncSession,
    stage_id: str,
) -> StageEvaluationWorkspaceRead:
    return await service.get_evaluation_workspace(db, ctx.organization.id, stage_id)


async def handle_generate_evaluation_workspace(
    ctx: MemberContext,
    db: AsyncSession,
    stage_id: str,
) -> StageEvaluationWorkspaceRead:
    return await service.generate_evaluation_workspace(
        db,
        ctx.organization.id,
        ctx.organization.name,
        ctx.member.id,
        ctx.member.userId,
        stage_id,
    )
