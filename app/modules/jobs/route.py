from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.controller import (
    handle_apply_public_posting,
    handle_approve_requisition,
    handle_close_requisition,
    handle_create_default_pipeline,
    handle_create_pipeline_stage,
    handle_create_requisition,
    handle_get_job_form_meta,
    handle_get_import_options,
    handle_get_public_posting,
    handle_get_requisition,
    handle_get_requisition_activity,
    handle_get_requisition_ai_analysis,
    handle_get_requisition_pipeline,
    handle_import_pipeline,
    handle_list_public_postings,
    handle_list_requisitions,
    handle_re_evaluate_requisition,
    handle_rebuild_requisition_ai_analysis,
    handle_reject_requisition,
    handle_reopen_requisition,
    handle_submit_requisition,
    handle_update_requisition,
)
from app.modules.jobs.schema import (
    CreatePipelineStageRequest,
    ImportableJobPostingRead,
    ImportPipelineRequest,
    JobFormMetaRead,
    JobRequisitionAiAnalysisRead,
    JobRequisitionCreateRequest,
    JobRequisitionDecisionRequest,
    JobRequisitionDetailRead,
    JobRequisitionListItemRead,
    JobRequisitionUpdateRequest,
    PipelineBoardRead,
    PipelineStageRead,
    PublicJobApplicationRead,
    PublicJobApplicationRequest,
    PublicJobPostingDetailRead,
    PublicJobPostingListItemRead,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.deps.permissions import require_permission
from app.shared.utils.permissions import get_member_permission_scope

router = APIRouter(prefix="/jobs", tags=["jobs"])


_SCOPE_RANK = {"none": 0, None: 0, "self": 1, "team": 2, "department": 3, "organization": 4}


def _pick_best_scope(*scopes: str | None) -> str | None:
    """Return the highest-ranked scope from the provided options."""
    valid = [s for s in scopes if s]
    if not valid:
        return None
    return max(valid, key=lambda s: _SCOPE_RANK.get(s, 0))


def require_requisition_view_or_approve(
    ctx: MemberContext = Depends(get_member_context),
    view_scope_override: str | None = Query(None, alias="view_scope"),
) -> MemberContext:
    view_scope = get_member_permission_scope(ctx.member, "jobs", "view")
    approve_scope = get_member_permission_scope(ctx.member, "jobs", "approve")
    best = _pick_best_scope(view_scope, approve_scope)
    if best is None or _SCOPE_RANK.get(best, 0) == 0:
        ctx.scope = "public_open"  # type: ignore[attr-defined]
        return ctx

    if view_scope_override and _SCOPE_RANK.get(view_scope_override, 0) <= _SCOPE_RANK[best]:
        ctx.scope = view_scope_override  # type: ignore[attr-defined]
        return ctx

    ctx.scope = best  # type: ignore[attr-defined]
    return ctx


def require_requisition_pipeline_edit(
    ctx: MemberContext = Depends(get_member_context),
) -> MemberContext:
    edit_scope = get_member_permission_scope(ctx.member, "jobs", "edit")
    approve_scope = get_member_permission_scope(ctx.member, "jobs", "approve")
    best = _pick_best_scope(edit_scope, approve_scope)
    if best is None or _SCOPE_RANK.get(best, 0) == 0:
        raise HTTPException(status_code=403, detail="you dont have permission")
    ctx.scope = best  # type: ignore[attr-defined]
    return ctx


def require_job_form_meta_access(
    ctx: MemberContext = Depends(get_member_context),
) -> MemberContext:
    create_scope = get_member_permission_scope(ctx.member, "jobs", "create")
    view_scope = get_member_permission_scope(ctx.member, "jobs", "view")
    approve_scope = get_member_permission_scope(ctx.member, "jobs", "approve")
    best = _pick_best_scope(create_scope, view_scope, approve_scope)
    if best is None or _SCOPE_RANK.get(best, 0) == 0:
        raise HTTPException(status_code=403, detail="you dont have permission")
    ctx.scope = best  # type: ignore[attr-defined]
    return ctx


@router.get("/requisitions", response_model=list[JobRequisitionListItemRead])
async def list_requisitions(
    ctx: Annotated[MemberContext, Depends(require_requisition_view_or_approve)],
    db: AsyncSession = Depends(get_db),
) -> list[JobRequisitionListItemRead]:
    return await handle_list_requisitions(ctx, db)


@router.get("/meta", response_model=JobFormMetaRead)
async def get_job_form_meta(
    ctx: Annotated[MemberContext, Depends(require_job_form_meta_access)],
    db: AsyncSession = Depends(get_db),
) -> JobFormMetaRead:
    return await handle_get_job_form_meta(ctx, db)


@router.get("/requisitions/{requisition_id}", response_model=JobRequisitionDetailRead)
async def get_requisition(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_requisition_view_or_approve)],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionDetailRead:
    return await handle_get_requisition(ctx, db, requisition_id)


@router.post("/requisitions", response_model=JobRequisitionDetailRead)
async def create_requisition(
    body: JobRequisitionCreateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "create", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionDetailRead:
    return await handle_create_requisition(ctx, db, body)


@router.patch("/requisitions/{requisition_id}", response_model=JobRequisitionDetailRead)
async def update_requisition(
    requisition_id: str,
    body: JobRequisitionUpdateRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "create", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionDetailRead:
    return await handle_update_requisition(ctx, db, requisition_id, body)


@router.post("/requisitions/{requisition_id}/submit", response_model=JobRequisitionDetailRead)
async def submit_requisition(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "create", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionDetailRead:
    return await handle_submit_requisition(ctx, db, requisition_id)


@router.post("/requisitions/{requisition_id}/approve", response_model=JobRequisitionDetailRead)
async def approve_requisition(
    requisition_id: str,
    body: JobRequisitionDecisionRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "approve"))],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionDetailRead:
    return await handle_approve_requisition(ctx, db, requisition_id, body)


@router.post("/requisitions/{requisition_id}/reject", response_model=JobRequisitionDetailRead)
async def reject_requisition(
    requisition_id: str,
    body: JobRequisitionDecisionRequest,
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "approve"))],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionDetailRead:
    return await handle_reject_requisition(ctx, db, requisition_id, body)


@router.patch("/requisitions/{requisition_id}/close", response_model=JobRequisitionDetailRead)
async def close_requisition(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "delete", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionDetailRead:
    return await handle_close_requisition(ctx, db, requisition_id)


@router.post("/requisitions/{requisition_id}/reopen", response_model=JobRequisitionDetailRead)
async def reopen_requisition(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "create", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionDetailRead:
    return await handle_reopen_requisition(ctx, db, requisition_id)


@router.get("/requisitions/{requisition_id}/activity")
async def get_requisition_activity(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_requisition_view_or_approve)],
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await handle_get_requisition_activity(ctx, db, requisition_id)


@router.get("/requisitions/{requisition_id}/ai-analysis", response_model=JobRequisitionAiAnalysisRead)
async def get_requisition_ai_analysis(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_requisition_view_or_approve)],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionAiAnalysisRead:
    return await handle_get_requisition_ai_analysis(ctx, db, requisition_id)


@router.post("/requisitions/{requisition_id}/ai-analysis/rebuild", response_model=JobRequisitionAiAnalysisRead)
async def rebuild_requisition_ai_analysis(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_requisition_pipeline_edit)],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionAiAnalysisRead:
    return await handle_rebuild_requisition_ai_analysis(ctx, db, requisition_id)


@router.post("/requisitions/{requisition_id}/re-evaluate", response_model=JobRequisitionAiAnalysisRead)
async def re_evaluate_requisition(
    requisition_id: str,
    background_tasks: BackgroundTasks,
    ctx: Annotated[MemberContext, Depends(require_requisition_pipeline_edit)],
    db: AsyncSession = Depends(get_db),
) -> JobRequisitionAiAnalysisRead:
    return await handle_re_evaluate_requisition(ctx, db, requisition_id, background_tasks)


@router.get("/requisitions/{requisition_id}/pipeline", response_model=PipelineBoardRead)
async def get_requisition_pipeline(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_requisition_view_or_approve)],
    db: AsyncSession = Depends(get_db),
) -> PipelineBoardRead:
    return await handle_get_requisition_pipeline(ctx, db, requisition_id)


@router.post("/requisitions/{requisition_id}/pipeline/stages", response_model=PipelineStageRead)
async def create_pipeline_stage(
    requisition_id: str,
    body: CreatePipelineStageRequest,
    ctx: Annotated[MemberContext, Depends(require_requisition_pipeline_edit)],
    db: AsyncSession = Depends(get_db),
) -> PipelineStageRead:
    return await handle_create_pipeline_stage(ctx, db, requisition_id, body)


@router.post("/requisitions/{requisition_id}/pipeline/default", response_model=PipelineBoardRead)
async def create_default_pipeline(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_requisition_pipeline_edit)],
    db: AsyncSession = Depends(get_db),
) -> PipelineBoardRead:
    return await handle_create_default_pipeline(ctx, db, requisition_id)


@router.post("/requisitions/{requisition_id}/pipeline/import", response_model=PipelineBoardRead)
async def import_pipeline(
    requisition_id: str,
    body: ImportPipelineRequest,
    ctx: Annotated[MemberContext, Depends(require_requisition_pipeline_edit)],
    db: AsyncSession = Depends(get_db),
) -> PipelineBoardRead:
    return await handle_import_pipeline(ctx, db, requisition_id, body)


@router.get(
    "/requisitions/{requisition_id}/pipeline/import-options",
    response_model=list[ImportableJobPostingRead],
)
async def get_pipeline_import_options(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_requisition_view_or_approve)],
    db: AsyncSession = Depends(get_db),
) -> list[ImportableJobPostingRead]:
    return await handle_get_import_options(ctx, db, requisition_id)


@router.get("/public/postings", response_model=list[PublicJobPostingListItemRead])
async def list_public_postings(
    db: AsyncSession = Depends(get_db),
) -> list[PublicJobPostingListItemRead]:
    return await handle_list_public_postings(db)


@router.get("/public/postings/{posting_id}", response_model=PublicJobPostingDetailRead)
async def get_public_posting(
    posting_id: str,
    db: AsyncSession = Depends(get_db),
) -> PublicJobPostingDetailRead:
    return await handle_get_public_posting(db, posting_id)


@router.post("/public/postings/{posting_id}/apply", response_model=PublicJobApplicationRead)
async def apply_public_posting(
    posting_id: str,
    body: PublicJobApplicationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> PublicJobApplicationRead:
    return await handle_apply_public_posting(db, posting_id, body, background_tasks)
