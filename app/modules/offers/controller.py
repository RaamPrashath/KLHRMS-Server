from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.offers import service
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
from app.shared.deps.organization_member import MemberContext


async def handle_get_workspace(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
) -> OfferStageWorkspaceRead:
    return await service.get_workspace(db, ctx.organization.id, job_slug, stage_slug)


async def handle_list_templates(
    ctx: MemberContext,
    db: AsyncSession,
    search: str | None,
    status: str | None,
) -> list[OfferTemplateListItemRead]:
    return await service.list_templates(db, ctx.organization.id, search, status)


async def handle_create_template(
    ctx: MemberContext,
    db: AsyncSession,
    body: OfferTemplateCreateRequest,
) -> OfferTemplateRead:
    return await service.create_template(db, ctx.organization.id, ctx.member.id, body)


async def handle_get_template(
    ctx: MemberContext,
    db: AsyncSession,
    template_id: str,
) -> OfferTemplateRead:
    return await service.get_template(db, ctx.organization.id, template_id)


async def handle_update_template(
    ctx: MemberContext,
    db: AsyncSession,
    template_id: str,
    body: OfferTemplateUpdateRequest,
) -> OfferTemplateRead:
    return await service.update_template(db, ctx.organization.id, ctx.member.id, template_id, body)


async def handle_delete_template(
    ctx: MemberContext,
    db: AsyncSession,
    template_id: str,
) -> None:
    await service.delete_template(db, ctx.organization.id, template_id)


async def handle_copy_template(
    ctx: MemberContext,
    db: AsyncSession,
    template_id: str,
    body: OfferTemplateCopyRequest,
) -> OfferTemplateRead:
    return await service.copy_template(db, ctx.organization.id, ctx.member.id, template_id, body)


async def handle_create_category(
    ctx: MemberContext,
    db: AsyncSession,
    template_id: str,
    body: OfferTemplateCategoryCreateRequest,
) -> OfferTemplateCategoryRead:
    return await service.create_category(db, ctx.organization.id, template_id, body)


async def handle_upsert_section(
    ctx: MemberContext,
    db: AsyncSession,
    template_id: str,
    category_id: str,
    section_key: str,
    body: OfferTemplateSectionUpsertRequest,
) -> OfferTemplateSectionRead:
    return await service.upsert_section(
        db,
        ctx.organization.id,
        template_id,
        category_id,
        section_key,
        body,
    )


async def handle_validate_candidates(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
    body: OfferCandidateValidationRequest,
) -> OfferCandidateValidationResponse:
    return await service.validate_candidates(db, ctx.organization.id, job_slug, stage_slug, body)


async def handle_validate_download_candidates(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
    body: OfferCandidateValidationRequest,
) -> OfferCandidateValidationResponse:
    return await service.validate_download_candidates(db, ctx.organization.id, job_slug, stage_slug, body)


async def handle_download_offer_letters(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
    body: OfferDownloadCreateRequest,
) -> tuple[str, bytes]:
    return await service.generate_offer_download_archive(
        db,
        ctx.organization.id,
        job_slug,
        stage_slug,
        body,
    )


async def handle_create_dispatch_batch(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
    body: OfferDispatchCreateRequest,
    background_tasks: BackgroundTasks,
) -> OfferDispatchCreateResponse:
    return await service.create_dispatch_batch(
        db,
        ctx.organization.id,
        ctx.member.id,
        job_slug,
        stage_slug,
        body,
        background_tasks,
    )


async def handle_get_dispatch_batch(
    ctx: MemberContext,
    db: AsyncSession,
    batch_id: str,
) -> OfferDispatchBatchDetailRead:
    return await service.get_dispatch_batch(db, ctx.organization.id, batch_id)


async def handle_get_application_offer_letters(
    ctx: MemberContext,
    db: AsyncSession,
    application_id: str,
) -> OfferApplicationLettersRead:
    return await service.get_application_offer_letters(db, ctx.organization.id, application_id)


async def handle_retry_failed_dispatch_batch(
    ctx: MemberContext,
    db: AsyncSession,
    batch_id: str,
    background_tasks: BackgroundTasks,
) -> OfferDispatchBatchDetailRead:
    return await service.retry_failed_dispatch_batch(
        db,
        ctx.organization.id,
        batch_id,
        background_tasks,
    )
