from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recruitment import RequisitionApprovalDecision
from app.modules.jobs import service
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
from app.shared.deps.organization_member import MemberContext


async def handle_list_requisitions(
    ctx: MemberContext,
    db: AsyncSession,
) -> list[JobRequisitionListItemRead]:
    return await service.list_requisitions(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        view_scope=ctx.scope,  # type: ignore[attr-defined]
    )


async def handle_get_job_form_meta(
    ctx: MemberContext,
    db: AsyncSession,
) -> JobFormMetaRead:
    return await service.get_job_form_meta(
        db=db,
        organization_id=ctx.organization.id,
    )


async def handle_get_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> JobRequisitionDetailRead:
    return await service.get_requisition(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        view_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_get_requisition_ai_analysis(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> JobRequisitionAiAnalysisRead:
    return await service.get_requisition_ai_analysis(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        view_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_rebuild_requisition_ai_analysis(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> JobRequisitionAiAnalysisRead:
    return await service.rebuild_requisition_ai_analysis(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        edit_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_re_evaluate_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    background_tasks: BackgroundTasks,
) -> JobRequisitionAiAnalysisRead:
    return await service.re_evaluate_requisition(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        edit_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
        background_tasks=background_tasks,
    )


async def handle_create_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    body: JobRequisitionCreateRequest,
) -> JobRequisitionDetailRead:
    return await service.create_requisition(
        db=db,
        organization_id=ctx.organization.id,
        raised_by_id=ctx.member.id,
        body=body,
    )


async def handle_get_requisition_pipeline(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> PipelineBoardRead:
    return await service.get_requisition_pipeline(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        view_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_create_pipeline_stage(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    body: CreatePipelineStageRequest,
) -> PipelineStageRead:
    return await service.create_pipeline_stage(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        edit_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
        body=body,
    )


async def handle_create_default_pipeline(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> PipelineBoardRead:
    return await service.create_default_pipeline(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        edit_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_import_pipeline(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    body: ImportPipelineRequest,
) -> PipelineBoardRead:
    return await service.import_pipeline(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        edit_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
        body=body,
    )


async def handle_get_import_options(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> list[ImportableJobPostingRead]:
    return await service.get_import_options(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        view_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_update_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    body: JobRequisitionUpdateRequest,
) -> JobRequisitionDetailRead:
    return await service.update_requisition(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        requisition_id=requisition_id,
        body=body,
    )


async def handle_submit_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> JobRequisitionDetailRead:
    return await service.submit_requisition(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        requisition_id=requisition_id,
    )


async def handle_approve_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    body: JobRequisitionDecisionRequest,
) -> JobRequisitionDetailRead:
    return await service.decide_requisition(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        requisition_id=requisition_id,
        decision=RequisitionApprovalDecision.APPROVED,
        body=body,
    )


async def handle_reject_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    body: JobRequisitionDecisionRequest,
) -> JobRequisitionDetailRead:
    return await service.decide_requisition(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        requisition_id=requisition_id,
        decision=RequisitionApprovalDecision.REJECTED,
        body=body,
    )


async def handle_close_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> JobRequisitionDetailRead:
    return await service.close_requisition(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        delete_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_reopen_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> JobRequisitionDetailRead:
    return await service.reopen_requisition(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        create_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_get_requisition_activity(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> list[dict]:
    return await service.get_requisition_activity(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        view_scope=ctx.scope,  # type: ignore[attr-defined]
        requisition_id=requisition_id,
    )


async def handle_list_public_postings(
    db: AsyncSession,
) -> list[PublicJobPostingListItemRead]:
    return await service.list_public_postings(db=db)


async def handle_get_public_posting(
    db: AsyncSession,
    posting_id: str,
) -> PublicJobPostingDetailRead:
    return await service.get_public_posting(db=db, posting_id=posting_id)


async def handle_apply_public_posting(
    db: AsyncSession,
    posting_id: str,
    body: PublicJobApplicationRequest,
    background_tasks: BackgroundTasks,
) -> PublicJobApplicationRead:
    return await service.apply_to_public_posting(
        db=db,
        posting_id=posting_id,
        body=body,
        background_tasks=background_tasks,
    )
