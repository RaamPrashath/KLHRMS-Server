from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.offers.controller import (
    handle_copy_template,
    handle_create_category,
    handle_create_dispatch_batch,
    handle_create_template,
    handle_delete_template,
    handle_download_offer_letters,
    handle_get_application_offer_letters,
    handle_get_dispatch_batch,
    handle_get_template,
    handle_get_workspace,
    handle_list_templates,
    handle_retry_failed_dispatch_batch,
    handle_update_template,
    handle_upsert_section,
    handle_validate_candidates,
    handle_validate_download_candidates,
)
from app.modules.offers.schema import (
    OfferApplicationLettersRead,
    OfferCandidateValidationRequest,
    OfferCandidateValidationResponse,
    OfferDispatchBatchDetailRead,
    OfferDispatchCreateRequest,
    OfferDispatchCreateResponse,
    OfferDownloadCreateRequest,
    OfferStageWorkspaceRead,
    OfferTemplateCategoryCreateRequest,
    OfferTemplateCategoryRead,
    OfferTemplateCopyRequest,
    OfferTemplateCreateRequest,
    OfferTemplateListItemRead,
    OfferTemplateRead,
    OfferTemplateSectionRead,
    OfferTemplateSectionUpsertRequest,
    OfferTemplateUpdateRequest,
)
from app.modules.offers.storage import offer_template_asset_storage_path, upload_offer_file
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.deps.permissions import require_permission
from app.shared.utils.permissions import get_member_permission_scope

router = APIRouter(prefix="/offers", tags=["offers"])

MAX_TEMPLATE_ASSET_BYTES = 2 * 1024 * 1024
ALLOWED_TEMPLATE_ASSET_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def require_any_candidate_permission(*actions: str) -> Callable[..., MemberContext]:
    """Phase 2 uses the product rule: any org-scoped candidate action can manage offers."""

    def _dependency(ctx: MemberContext = Depends(get_member_context)) -> MemberContext:
        for action in actions:
            if get_member_permission_scope(ctx.member, "candidates", action) == "organization":
                ctx.scope = "organization"  # type: ignore[attr-defined]
                return ctx
        raise HTTPException(status_code=403, detail="you dont have permission")

    _dependency.__name__ = f"require_any_candidate_{'_'.join(actions)}"
    return _dependency


TemplateManageCtx = Annotated[
    MemberContext,
    Depends(require_any_candidate_permission("view", "create", "edit", "delete")),
]
SendOfferCtx = Annotated[
    MemberContext,
    Depends(require_any_candidate_permission("view", "create", "edit", "delete")),
]
ViewOfferCtx = Annotated[MemberContext, Depends(require_permission("candidates", "view"))]


@router.get(
    "/pipeline/jobs/{job_slug}/stages/{stage_slug}/workspace",
    response_model=OfferStageWorkspaceRead,
)
async def get_offer_workspace(
    job_slug: str,
    stage_slug: str,
    ctx: ViewOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferStageWorkspaceRead:
    return await handle_get_workspace(ctx, db, job_slug, stage_slug)


@router.post(
    "/pipeline/jobs/{job_slug}/stages/{stage_slug}/validate",
    response_model=OfferCandidateValidationResponse,
)
async def validate_offer_candidates(
    job_slug: str,
    stage_slug: str,
    body: OfferCandidateValidationRequest,
    ctx: SendOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferCandidateValidationResponse:
    return await handle_validate_candidates(ctx, db, job_slug, stage_slug, body)


@router.post(
    "/pipeline/jobs/{job_slug}/stages/{stage_slug}/download/validate",
    response_model=OfferCandidateValidationResponse,
)
async def validate_offer_download_candidates(
    job_slug: str,
    stage_slug: str,
    body: OfferCandidateValidationRequest,
    ctx: SendOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferCandidateValidationResponse:
    return await handle_validate_download_candidates(ctx, db, job_slug, stage_slug, body)


@router.post("/pipeline/jobs/{job_slug}/stages/{stage_slug}/download")
async def download_offer_letters(
    job_slug: str,
    stage_slug: str,
    body: OfferDownloadCreateRequest,
    ctx: SendOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> Response:
    file_name, content = await handle_download_offer_letters(ctx, db, job_slug, stage_slug, body)
    encoded_file_name = quote(file_name)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{file_name}\"; filename*=UTF-8''{encoded_file_name}"
            ),
        },
    )


@router.post(
    "/pipeline/jobs/{job_slug}/stages/{stage_slug}/dispatch",
    response_model=OfferDispatchCreateResponse,
)
async def create_offer_dispatch(
    job_slug: str,
    stage_slug: str,
    body: OfferDispatchCreateRequest,
    background_tasks: BackgroundTasks,
    ctx: SendOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferDispatchCreateResponse:
    return await handle_create_dispatch_batch(ctx, db, job_slug, stage_slug, body, background_tasks)


@router.get("/batches/{batch_id}", response_model=OfferDispatchBatchDetailRead)
async def get_offer_dispatch_batch(
    batch_id: str,
    ctx: ViewOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferDispatchBatchDetailRead:
    return await handle_get_dispatch_batch(ctx, db, batch_id)


@router.post("/batches/{batch_id}/retry-failed", response_model=OfferDispatchBatchDetailRead)
async def retry_failed_offer_dispatch_batch(
    batch_id: str,
    background_tasks: BackgroundTasks,
    ctx: SendOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferDispatchBatchDetailRead:
    return await handle_retry_failed_dispatch_batch(ctx, db, batch_id, background_tasks)


@router.get("/applications/{application_id}", response_model=OfferApplicationLettersRead)
async def get_application_offer_letters(
    application_id: str,
    ctx: ViewOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferApplicationLettersRead:
    return await handle_get_application_offer_letters(ctx, db, application_id)


@router.get("/templates", response_model=list[OfferTemplateListItemRead])
async def list_offer_templates(
    ctx: ViewOfferCtx,
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=120),
    status: str | None = Query(default=None, max_length=32),
) -> list[OfferTemplateListItemRead]:
    return await handle_list_templates(ctx, db, search, status)


@router.post("/templates", response_model=OfferTemplateRead)
async def create_offer_template(
    body: OfferTemplateCreateRequest,
    ctx: TemplateManageCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferTemplateRead:
    return await handle_create_template(ctx, db, body)


@router.get("/templates/{template_id}", response_model=OfferTemplateRead)
async def get_offer_template(
    template_id: str,
    ctx: ViewOfferCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferTemplateRead:
    return await handle_get_template(ctx, db, template_id)


@router.patch("/templates/{template_id}", response_model=OfferTemplateRead)
async def update_offer_template(
    template_id: str,
    body: OfferTemplateUpdateRequest,
    ctx: TemplateManageCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferTemplateRead:
    return await handle_update_template(ctx, db, template_id, body)


@router.post("/templates/{template_id}/assets", response_model=dict[str, str])
async def upload_offer_template_asset(
    template_id: str,
    ctx: TemplateManageCtx,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await handle_get_template(ctx, db, template_id)
    extension = ALLOWED_TEMPLATE_ASSET_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(status_code=400, detail="Upload a PNG, JPG, WEBP, or SVG image")

    content = await file.read(MAX_TEMPLATE_ASSET_BYTES + 1)
    if len(content) > MAX_TEMPLATE_ASSET_BYTES:
        raise HTTPException(status_code=400, detail="Image must be 2 MB or smaller")

    storage_path = offer_template_asset_storage_path(
        organization_id=ctx.organization.id,
        template_id=template_id,
        extension=extension,
    )
    try:
        upload = await upload_offer_file(
            content=content,
            storage_path=storage_path,
            content_type=file.content_type or "application/octet-stream",
            upsert=False,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"url": upload.public_url}


@router.delete("/templates/{template_id}", status_code=204)
async def delete_offer_template(
    template_id: str,
    ctx: TemplateManageCtx,
    db: AsyncSession = Depends(get_db),
) -> Response:
    await handle_delete_template(ctx, db, template_id)
    return Response(status_code=204)


@router.post("/templates/{template_id}/copy", response_model=OfferTemplateRead)
async def copy_offer_template(
    template_id: str,
    body: OfferTemplateCopyRequest,
    ctx: TemplateManageCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferTemplateRead:
    return await handle_copy_template(ctx, db, template_id, body)


@router.post(
    "/templates/{template_id}/categories",
    response_model=OfferTemplateCategoryRead,
)
async def create_offer_template_category(
    template_id: str,
    body: OfferTemplateCategoryCreateRequest,
    ctx: TemplateManageCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferTemplateCategoryRead:
    return await handle_create_category(ctx, db, template_id, body)


@router.put(
    "/templates/{template_id}/categories/{category_id}/sections/{section_key}",
    response_model=OfferTemplateSectionRead,
)
async def upsert_offer_template_section(
    template_id: str,
    category_id: str,
    section_key: str,
    body: OfferTemplateSectionUpsertRequest,
    ctx: TemplateManageCtx,
    db: AsyncSession = Depends(get_db),
) -> OfferTemplateSectionRead:
    return await handle_upsert_section(ctx, db, template_id, category_id, section_key, body)
