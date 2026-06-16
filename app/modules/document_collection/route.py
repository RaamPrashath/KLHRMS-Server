from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.document_collection import service
from app.modules.document_collection.schema import (
    DocumentCollectionRequestDetailRead,
    DocumentCollectionSendRequest,
    DocumentCollectionSendResponse,
    DocumentCollectionTemplateCopyRequest,
    DocumentCollectionTemplateCreateRequest,
    DocumentCollectionTemplateListItemRead,
    DocumentCollectionTemplateRead,
    DocumentCollectionTemplateUpdateRequest,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.utils.permissions import get_member_permission_scope

router = APIRouter(prefix="/document-collection", tags=["document-collection"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
MemberCtx = Annotated[MemberContext, Depends(get_member_context)]


def require_document_collection_manage() -> Callable[..., MemberContext]:
    """
    Prefer the dedicated documentCollection permission, but keep older
    candidate-manager roles working until role JSON is backfilled.
    """

    def _dependency(ctx: MemberCtx) -> MemberContext:
        for action in ("create", "edit", "delete", "view"):
            if get_member_permission_scope(ctx.member, "documentCollection", action) in {
                "department",
                "organization",
            }:
                ctx.scope = "organization"  # type: ignore[attr-defined]
                return ctx
        for action in ("view", "create", "edit", "delete"):
            if get_member_permission_scope(ctx.member, "candidates", action) == "organization":
                ctx.scope = "organization"  # type: ignore[attr-defined]
                return ctx
        raise HTTPException(status_code=403, detail="you dont have permission")

    _dependency.__name__ = "require_document_collection_manage"
    return _dependency


DocumentCollectionManageCtx = Annotated[MemberContext, Depends(require_document_collection_manage())]


@router.get("/templates", response_model=list[DocumentCollectionTemplateListItemRead])
async def list_templates(
    ctx: DocumentCollectionManageCtx,
    db: DbSession,
    search: str | None = None,
    status: str | None = None,
) -> list[DocumentCollectionTemplateListItemRead]:
    return await service.list_templates(db, ctx.organization.id, search, status)


@router.post("/templates", response_model=DocumentCollectionTemplateRead)
async def create_template(
    body: DocumentCollectionTemplateCreateRequest,
    ctx: DocumentCollectionManageCtx,
    db: DbSession,
) -> DocumentCollectionTemplateRead:
    return await service.create_template(db, ctx.organization.id, ctx.member.id, body)


@router.get("/templates/{template_id}", response_model=DocumentCollectionTemplateRead)
async def get_template(
    template_id: str,
    ctx: DocumentCollectionManageCtx,
    db: DbSession,
) -> DocumentCollectionTemplateRead:
    return await service.get_template(db, ctx.organization.id, template_id)


@router.get("/requests/{request_id}", response_model=DocumentCollectionRequestDetailRead)
async def get_request_detail(
    request_id: str,
    ctx: DocumentCollectionManageCtx,
    db: DbSession,
) -> DocumentCollectionRequestDetailRead:
    return await service.get_request_detail(db, ctx.organization.id, request_id)


@router.patch("/templates/{template_id}", response_model=DocumentCollectionTemplateRead)
async def update_template(
    template_id: str,
    body: DocumentCollectionTemplateUpdateRequest,
    ctx: DocumentCollectionManageCtx,
    db: DbSession,
) -> DocumentCollectionTemplateRead:
    return await service.update_template(db, ctx.organization.id, ctx.member.id, template_id, body)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    ctx: DocumentCollectionManageCtx,
    db: DbSession,
) -> None:
    await service.delete_template(db, ctx.organization.id, template_id)


@router.post("/templates/{template_id}/copy", response_model=DocumentCollectionTemplateRead)
async def copy_template(
    template_id: str,
    body: DocumentCollectionTemplateCopyRequest,
    ctx: DocumentCollectionManageCtx,
    db: DbSession,
) -> DocumentCollectionTemplateRead:
    return await service.copy_template(db, ctx.organization.id, ctx.member.id, template_id, body)


@router.post(
    "/pipeline/jobs/{job_slug}/stages/{stage_slug}/send-requests",
    response_model=DocumentCollectionSendResponse,
)
async def send_requests(
    job_slug: str,
    stage_slug: str,
    body: DocumentCollectionSendRequest,
    background_tasks: BackgroundTasks,
    ctx: DocumentCollectionManageCtx,
    db: DbSession,
) -> DocumentCollectionSendResponse:
    return await service.send_requests(
        db,
        ctx.organization.id,
        ctx.member.id,
        job_slug,
        stage_slug,
        body,
        background_tasks,
    )
