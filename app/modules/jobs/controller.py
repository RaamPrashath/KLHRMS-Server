from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recruitment import RequisitionApprovalDecision
from app.modules.jobs import service
from app.modules.jobs.schema import (
    JobRequisitionCreateRequest,
    JobRequisitionDecisionRequest,
    JobRequisitionDetailRead,
    JobRequisitionListItemRead,
    PublicJobApplicationRead,
    PublicJobApplicationRequest,
    PublicJobPostingDetailRead,
    PublicJobPostingListItemRead,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_requisitions(
    ctx: MemberContext,
    db: AsyncSession,
    owned_only: bool,
) -> list[JobRequisitionListItemRead]:
    return await service.list_requisitions(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        view_scope=ctx.scope,  # type: ignore[attr-defined]
        owned_only=owned_only,
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
) -> PublicJobApplicationRead:
    return await service.apply_to_public_posting(
        db=db,
        posting_id=posting_id,
        body=body,
    )
