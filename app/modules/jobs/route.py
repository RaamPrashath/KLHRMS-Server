from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.controller import (
    handle_approve_requisition,
    handle_apply_public_posting,
    handle_close_requisition,
    handle_create_requisition,
    handle_get_public_posting,
    handle_get_requisition,
    handle_list_public_postings,
    handle_list_requisitions,
    handle_reject_requisition,
    handle_submit_requisition,
)
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
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/requisitions", response_model=list[JobRequisitionListItemRead])
async def list_requisitions(
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
) -> list[JobRequisitionListItemRead]:
    return await handle_list_requisitions(ctx, db)


@router.get("/requisitions/{requisition_id}", response_model=JobRequisitionDetailRead)
async def get_requisition(
    requisition_id: str,
    ctx: Annotated[MemberContext, Depends(require_permission("jobs", "view", allow_self=True))],
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
    db: AsyncSession = Depends(get_db),
) -> PublicJobApplicationRead:
    return await handle_apply_public_posting(db, posting_id, body)
