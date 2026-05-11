from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.candidates.controller import (
    handle_complete_interview_meeting,
    handle_create_interview_meeting,
    handle_create_stage,
    handle_delete_stage,
    handle_extend_stage_due_date,
    handle_generate_evaluation_workspace,
    handle_get_application_detail,
    handle_get_evaluation_workspace,
    handle_get_pipeline_board,
    handle_list_job_postings,
    handle_move_application_stage,
    handle_update_stage,
)
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
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("/pipeline/postings", response_model=list[PipelineJobPostingRead])
async def list_pipeline_job_postings(
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view"))],
    db: AsyncSession = Depends(get_db),
) -> list[PipelineJobPostingRead]:
    return await handle_list_job_postings(ctx, db)


@router.get("/pipeline", response_model=PipelineBoardRead)
async def get_pipeline_board(
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view"))],
    db: AsyncSession = Depends(get_db),
    jobPostingId: str = Query(min_length=1),
) -> PipelineBoardRead:
    return await handle_get_pipeline_board(ctx, db, jobPostingId)


@router.patch("/applications/{application_id}/stage", response_model=PipelineApplicationRead)
async def move_application_stage(
    application_id: str,
    body: MoveApplicationStageRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> PipelineApplicationRead:
    return await handle_move_application_stage(ctx, db, application_id, body)


@router.get("/applications/{application_id}", response_model=CandidateApplicationDetailRead)
async def get_application_detail(
    application_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view"))],
    db: AsyncSession = Depends(get_db),
) -> CandidateApplicationDetailRead:
    return await handle_get_application_detail(ctx, db, application_id)


@router.post("/applications/{application_id}/interview-meetings", response_model=InterviewMeetingRead)
async def create_interview_meeting(
    application_id: str,
    body: InterviewMeetingCreateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> InterviewMeetingRead:
    return await handle_create_interview_meeting(ctx, db, application_id, body)


@router.post("/applications/{application_id}/interview-meetings/{event_id}/complete", response_model=InterviewMeetingRead)
async def complete_interview_meeting(
    application_id: str,
    event_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> InterviewMeetingRead:
    return await handle_complete_interview_meeting(ctx, db, application_id, event_id)


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


@router.get("/pipeline/stages/{stage_id}/evaluation-workspace", response_model=StageEvaluationWorkspaceRead)
async def get_evaluation_workspace(
    stage_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "view"))],
    db: AsyncSession = Depends(get_db),
) -> StageEvaluationWorkspaceRead:
    return await handle_get_evaluation_workspace(ctx, db, stage_id)


@router.post("/pipeline/stages/{stage_id}/evaluation-workspace", response_model=StageEvaluationWorkspaceRead)
async def generate_evaluation_workspace(
    stage_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "edit"))],
    db: AsyncSession = Depends(get_db),
) -> StageEvaluationWorkspaceRead:
    return await handle_generate_evaluation_workspace(ctx, db, stage_id)


@router.delete("/pipeline/stages/{stage_id}", status_code=204)
async def delete_pipeline_stage(
    stage_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("candidates", "delete"))],
    db: AsyncSession = Depends(get_db),
) -> Response:
    await handle_delete_stage(ctx, db, stage_id)
    return Response(status_code=204)
