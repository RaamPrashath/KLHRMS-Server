from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidates.controller import (
    handle_accept_interview,
    handle_assign_stage_interviews,
    handle_complete_interview_meeting,
    handle_complete_stage,
    handle_create_application_note,
    handle_create_interview_meeting,
    handle_create_reassignment_request,
    handle_create_stage,
    handle_delete_stage,
    handle_distribute_stage_interviews,
    handle_extend_stage_due_date,
    handle_get_application_detail,
    handle_get_pipeline_board,
    handle_get_pipeline_board_by_job_slug,
    handle_get_stage_workspace,
    handle_get_stage_workspace_by_job_slug,
    handle_list_interviewers,
    handle_list_job_postings,
    handle_list_my_interviews,
    handle_move_application_stage,
    handle_move_interview_assignment,
    handle_preview_stage_interview_warnings,
    handle_reject_interview,
    handle_reopen_stage,
    handle_reshuffle_interview_assignment,
    handle_start_interview_meeting,
    handle_update_application_detail,
    handle_update_application_note,
    handle_update_interview_meeting,
    handle_update_stage,
)
from app.modules.candidates.schema import (
    CandidateApplicationDetailRead,
    CandidateApplicationNoteCreateRequest,
    CandidateApplicationNoteUpdateRequest,
    CandidateApplicationUpdateRequest,
    InterviewAcceptRequest,
    InterviewAcceptResponse,
    InterviewerSearchResponse,
    InterviewMeetingCompleteRequest,
    InterviewMeetingCreateRequest,
    InterviewMeetingRead,
    InterviewMeetingUpdateRequest,
    InterviewMoveRequest,
    InterviewMoveResponse,
    InterviewRejectResponse,
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
    StageInterviewAssignmentRequest,
    StageInterviewAssignmentResponse,
    StageInterviewWarningRequest,
    StageInterviewWarningResponse,
    StageWorkspaceRead,
    TeamDistributionRequest,
    TeamDistributionResponse,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_any_permission, require_permission

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/pipeline/postings", response_model=list[PipelineJobPostingRead])
async def list_pipeline_job_postings(
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> list[PipelineJobPostingRead]:
    return await handle_list_job_postings(ctx, db)


@router.get("/pipeline", response_model=PipelineBoardRead)
async def get_pipeline_board(
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
    jobPostingId: str = Query(min_length=1),
) -> PipelineBoardRead:
    return await handle_get_pipeline_board(ctx, db, jobPostingId)


@router.get("/pipeline/jobs/{job_slug}", response_model=PipelineBoardRead)
async def get_pipeline_board_by_job_slug(
    job_slug: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> PipelineBoardRead:
    return await handle_get_pipeline_board_by_job_slug(ctx, db, job_slug)


@router.get("/pipeline/interviewers", response_model=InterviewerSearchResponse)
async def list_interviewers(
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=120),
) -> InterviewerSearchResponse:
    return await handle_list_interviewers(ctx, db, search)


@router.get("/pipeline/stages/by-slug/{stage_slug}/workspace", response_model=StageWorkspaceRead)
async def get_stage_workspace(
    stage_slug: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view"))],
    db: AsyncSession = Depends(get_db),
) -> StageWorkspaceRead:
    return await handle_get_stage_workspace(ctx, db, stage_slug)


@router.get("/pipeline/jobs/{job_slug}/stages/{stage_slug}/workspace", response_model=StageWorkspaceRead)
async def get_stage_workspace_by_job_slug(
    job_slug: str,
    stage_slug: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view"))],
    db: AsyncSession = Depends(get_db),
) -> StageWorkspaceRead:
    return await handle_get_stage_workspace_by_job_slug(ctx, db, job_slug, stage_slug)


@router.post(
    "/pipeline/stages/by-slug/{stage_slug}/assignments/warnings",
    response_model=StageInterviewWarningResponse,
)
async def preview_stage_interview_warnings(
    stage_slug: str,
    body: StageInterviewWarningRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> StageInterviewWarningResponse:
    return await handle_preview_stage_interview_warnings(ctx, db, stage_slug, body)


@router.post(
    "/pipeline/stages/by-slug/{stage_slug}/assignments",
    response_model=StageInterviewAssignmentResponse,
)
async def assign_stage_interviews(
    stage_slug: str,
    body: StageInterviewAssignmentRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> StageInterviewAssignmentResponse:
    return await handle_assign_stage_interviews(ctx, db, stage_slug, body)


@router.patch("/applications/{application_id}/stage", response_model=PipelineApplicationRead)
async def move_application_stage(
    application_id: str,
    body: MoveApplicationStageRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> PipelineApplicationRead:
    return await handle_move_application_stage(ctx, db, application_id, body)


@router.post("/applications/{application_id}/move", response_model=PipelineApplicationRead)
async def move_application_stage_legacy(
    application_id: str,
    body: MoveApplicationStageRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> PipelineApplicationRead:
    return await handle_move_application_stage(ctx, db, application_id, body)


@router.get("/applications/{application_id}", response_model=CandidateApplicationDetailRead)
async def get_application_detail(
    application_id: str,
    ctx: Annotated[MemberContext, Depends(require_any_permission(("candidates", "view"), ("interviews", "view"), ("jobs", "view")))],
    db: AsyncSession = Depends(get_db),
) -> CandidateApplicationDetailRead:
    return await handle_get_application_detail(ctx, db, application_id)


@router.patch("/applications/{application_id}", response_model=CandidateApplicationDetailRead)
async def update_application_detail(
    application_id: str,
    body: CandidateApplicationUpdateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> CandidateApplicationDetailRead:
    return await handle_update_application_detail(ctx, db, application_id, body)


@router.post("/applications/{application_id}/notes", response_model=CandidateApplicationDetailRead)
async def create_application_note(
    application_id: str,
    body: CandidateApplicationNoteCreateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> CandidateApplicationDetailRead:
    return await handle_create_application_note(ctx, db, application_id, body)


@router.patch("/applications/{application_id}/notes/{note_id}", response_model=CandidateApplicationDetailRead)
async def update_application_note(
    application_id: str,
    note_id: str,
    body: CandidateApplicationNoteUpdateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> CandidateApplicationDetailRead:
    return await handle_update_application_note(ctx, db, application_id, note_id, body)


@router.post("/applications/{application_id}/interview-meetings", response_model=InterviewMeetingRead)
async def create_interview_meeting(
    application_id: str,
    body: InterviewMeetingCreateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "create"))],
    db: AsyncSession = Depends(get_db),
) -> InterviewMeetingRead:
    return await handle_create_interview_meeting(ctx, db, application_id, body)


@router.post("/applications/{application_id}/interview-meetings/{event_id}/complete", response_model=InterviewMeetingRead)
async def complete_interview_meeting(
    application_id: str,
    event_id: str,
    body: InterviewMeetingCompleteRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> InterviewMeetingRead:
    return await handle_complete_interview_meeting(ctx, db, application_id, event_id, body)


@router.patch("/applications/{application_id}/interview-meetings/{event_id}", response_model=InterviewMeetingRead)
async def update_interview_meeting(
    application_id: str,
    event_id: str,
    body: InterviewMeetingUpdateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> InterviewMeetingRead:
    return await handle_update_interview_meeting(ctx, db, application_id, event_id, body)


@router.post("/applications/{application_id}/interview-meetings/{event_id}/start", response_model=InterviewMeetingRead)
async def start_interview_meeting(
    application_id: str,
    event_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> InterviewMeetingRead:
    return await handle_start_interview_meeting(ctx, db, application_id, event_id)


@router.post("/pipeline/stages", response_model=PipelineStageRead)
async def create_pipeline_stage(
    body: PipelineStageCreateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> PipelineStageRead:
    return await handle_create_stage(ctx, db, body)


@router.patch("/pipeline/stages/{stage_id}", response_model=PipelineStageRead)
async def update_pipeline_stage(
    stage_id: str,
    body: PipelineStageUpdateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> PipelineStageRead:
    return await handle_update_stage(ctx, db, stage_id, body)


@router.post("/pipeline/stages/{stage_id}/extend", response_model=PipelineStageRead)
async def extend_pipeline_stage_due_date(
    stage_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> PipelineStageRead:
    return await handle_extend_stage_due_date(ctx, db, stage_id)


@router.post("/pipeline/stages/{stage_id}/complete", response_model=PipelineStageRead)
async def complete_pipeline_stage(
    stage_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> PipelineStageRead:
    return await handle_complete_stage(ctx, db, stage_id)


@router.post("/pipeline/stages/{stage_id}/reopen", response_model=PipelineStageRead)
async def reopen_pipeline_stage(
    stage_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> PipelineStageRead:
    return await handle_reopen_stage(ctx, db, stage_id)


@router.delete("/pipeline/stages/{stage_id}", status_code=204)
async def delete_pipeline_stage(
    stage_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "delete"))],
    db: AsyncSession = Depends(get_db),
) -> Response:
    await handle_delete_stage(ctx, db, stage_id)
    return Response(status_code=204)


@router.post(
    "/pipeline/stages/by-slug/{stage_slug}/team-assignments",
    response_model=TeamDistributionResponse,
)
async def distribute_stage_interviews(
    stage_slug: str,
    body: TeamDistributionRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> TeamDistributionResponse:
    return await handle_distribute_stage_interviews(ctx, db, stage_slug, body)


@router.post(
    "/applications/{application_id}/interview-events/{event_id}/move",
    response_model=InterviewMoveResponse,
)
async def move_interview_assignment(
    application_id: str,
    event_id: str,
    body: InterviewMoveRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> InterviewMoveResponse:
    return await handle_move_interview_assignment(ctx, db, application_id, event_id, body)


@router.post(
    "/applications/{application_id}/interview-events/{event_id}/reshuffle",
    response_model=ReshuffleResponse,
)
async def reshuffle_interview_assignment(
    application_id: str,
    event_id: str,
    body: ReshuffleRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> ReshuffleResponse:
    return await handle_reshuffle_interview_assignment(ctx, db, application_id, event_id, body)


@router.get("/interviews/my", response_model=MyInterviewListResponse)
async def list_my_interviews(
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> MyInterviewListResponse:
    return await handle_list_my_interviews(ctx, db)


@router.post("/interviews/{event_id}/accept", response_model=InterviewAcceptResponse)
async def accept_interview(
    event_id: str,
    body: InterviewAcceptRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> InterviewAcceptResponse:
    return await handle_accept_interview(ctx, db, event_id, body)


@router.post("/interviews/{event_id}/reject", response_model=InterviewRejectResponse)
async def reject_interview(
    event_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "edit", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> InterviewRejectResponse:
    return await handle_reject_interview(ctx, db, event_id)


@router.post("/interviews/{event_id}/reassignment-requests")
async def create_reassignment_request(
    event_id: str,
    body: ReassignmentRequestCreate,
    ctx: Annotated[MemberContext, Depends(require_permission("interviews", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> Response:
    body.eventId = event_id
    await handle_create_reassignment_request(ctx, db, body)
    return Response(status_code=201)
