from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidates import service
from app.modules.candidates.schema import (
    CandidateApplicationDetailRead,
    CandidateApplicationNoteCreateRequest,
    CandidateApplicationNoteUpdateRequest,
    CandidateApplicationUpdateRequest,
    InterviewerSearchResponse,
    InterviewMeetingCreateRequest,
    InterviewMeetingCompleteRequest,
    InterviewMeetingRead,
    MoveApplicationStageRequest,
    MyInterviewListResponse,
    PipelineApplicationRead,
    PipelineBoardRead,
    PipelineJobPostingRead,
    PipelineStageCreateRequest,
    PipelineStageRead,
    PipelineStageUpdateRequest,
    ReassignmentRequestCreate,
    ReshuffleRequest,
    ReshuffleResponse,
    StageEvaluationWorkspaceRead,
    StageInterviewAssignmentRequest,
    StageInterviewAssignmentResponse,
    StageInterviewWarningRequest,
    StageInterviewWarningResponse,
    StageWorkspaceRead,
    TeamDistributionRequest,
    TeamDistributionResponse,
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


async def handle_get_pipeline_board_by_job_slug(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
) -> PipelineBoardRead:
    return await service.get_pipeline_board_by_job_slug(db, ctx.organization.id, job_slug)


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
    return await service.get_application_detail(db, ctx.organization.id, ctx.member.id, application_id)


async def handle_update_application_detail(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
    body: CandidateApplicationUpdateRequest,
) -> CandidateApplicationDetailRead:
    return await service.update_candidate_application(db, ctx.organization.id, ctx.member.id, application_id, body)


async def handle_create_application_note(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
    body: CandidateApplicationNoteCreateRequest,
) -> CandidateApplicationDetailRead:
    return await service.create_application_note(
        db,
        ctx.organization.id,
        ctx.member.id,
        application_id,
        body,
    )


async def handle_update_application_note(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
    note_id: str,
    body: CandidateApplicationNoteUpdateRequest,
) -> CandidateApplicationDetailRead:
    return await service.update_application_note(
        db,
        ctx.organization.id,
        ctx.member.id,
        application_id,
        note_id,
        body,
    )


async def handle_get_stage_workspace(
    ctx: MemberContext,
    db: AsyncSession,
    stage_slug: str,
) -> StageWorkspaceRead:
    return await service.get_stage_workspace(db, ctx.organization.id, stage_slug)


async def handle_get_stage_workspace_by_job_slug(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
) -> StageWorkspaceRead:
    return await service.get_stage_workspace_by_job_slug(db, ctx.organization.id, job_slug, stage_slug)


async def handle_list_interviewers(
    ctx: MemberContext,
    db: AsyncSession,
    search: str | None,
) -> InterviewerSearchResponse:
    return await service.search_interviewers(db, ctx.organization.id, search)


async def handle_preview_stage_interview_warnings(
    ctx: MemberContext,
    db: AsyncSession,
    stage_slug: str,
    body: StageInterviewWarningRequest,
) -> StageInterviewWarningResponse:
    return await service.preview_stage_interview_warnings(db, ctx.organization.id, stage_slug, body)


async def handle_assign_stage_interviews(
    ctx: MemberContext,
    db: AsyncSession,
    stage_slug: str,
    body: StageInterviewAssignmentRequest,
) -> StageInterviewAssignmentResponse:
    return await service.assign_stage_interviews(
        db,
        ctx.organization.id,
        ctx.organization.name,
        ctx.member.id,
        stage_slug,
        body,
    )


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
    body: InterviewMeetingCompleteRequest,
) -> InterviewMeetingRead:
    return await service.complete_interview_meeting(
        db,
        ctx.organization.id,
        application_id,
        event_id,
        ctx.member.id,
        ctx.member.userId,
        body,
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


async def handle_distribute_stage_interviews(
    ctx: MemberContext,
    db: AsyncSession,
    stage_slug: str,
    body: TeamDistributionRequest,
) -> TeamDistributionResponse:
    return await service.distribute_stage_interviews(
        db,
        ctx.organization.id,
        ctx.organization.name,
        ctx.member.id,
        stage_slug,
        body,
    )


async def handle_reshuffle_interview_assignment(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
    event_id: str,
    body: ReshuffleRequest,
) -> ReshuffleResponse:
    return await service.reshuffle_interview_assignment(
        db,
        ctx.organization.id,
        ctx.organization.name,
        ctx.member.id,
        application_id,
        event_id,
        body,
    )


async def handle_list_my_interviews(
    ctx: MemberContext,
    db: AsyncSession,
) -> MyInterviewListResponse:
    return await service.list_my_interviews(
        db,
        ctx.organization.id,
        ctx.member.id,
    )


async def handle_create_reassignment_request(
    ctx: MemberContext,
    db: AsyncSession,
    body: ReassignmentRequestCreate,
) -> None:
    return await service.create_reassignment_request(
        db,
        ctx.organization.id,
        ctx.organization.name,
        ctx.member.id,
        body,
    )
