from __future__ import annotations

import re
import secrets
from copy import deepcopy
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.resend_service import ResendEmailService
from app.models.organization import Organization
from app.models.recruitment import (
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    JobPosting,
    JobRequisition,
    OfferDispatchBatch,
    OfferDispatchBatchStatus,
    OfferLetter,
    OfferStatus,
    OfferTemplate,
    OfferTemplateCategory,
    OfferTemplateSection,
    OfferTemplateStatus,
    PipelineStage,
    StageType,
)
from app.modules.offers.render import (
    OfferRenderError,
    render_offer_docx,
    render_offer_html,
    render_offer_pdf,
)
from app.modules.offers.repository import OfferRepository
from app.modules.offers.schema import (
    COMPENSATION_VARIABLE_TOKENS,
    VARIABLE_PATTERN,
    OfferApplicationLettersRead,
    OfferCandidateSummaryRead,
    OfferCandidateValidationRequest,
    OfferCandidateValidationResponse,
    OfferCandidateValidationResultRead,
    OfferDispatchBatchDetailRead,
    OfferDispatchBatchRead,
    OfferDispatchCreateRequest,
    OfferDispatchCreateResponse,
    OfferDownloadCreateRequest,
    OfferEligibilityRead,
    OfferJobCompensationPreviewRead,
    OfferJobPostingSummaryRead,
    OfferLetterRead,
    OfferStageSummaryRead,
    OfferStageWorkspaceRead,
    OfferTemplateCategoryCreateRequest,
    OfferTemplateCategoryInput,
    OfferTemplateCategoryRead,
    OfferTemplateCopyRequest,
    OfferTemplateCreateRequest,
    OfferTemplateListItemRead,
    OfferTemplateRead,
    OfferTemplateSectionRead,
    OfferTemplateSectionUpsertRequest,
    OfferTemplateSummaryRead,
    OfferTemplateUpdateRequest,
    sanitize_offer_html,
    validate_offer_variables,
)
from app.modules.offers.storage import (
    offer_storage_path,
    safe_offer_file_name,
    safe_offer_file_stem,
    upload_offer_pdf,
)
from app.shared.config import get_settings
from app.shared.database import AsyncSessionLocal
from app.shared.utils.slugs import generate_unique_slug

DEFAULT_SECTION_DEFINITIONS: list[tuple[str, str]] = [
    ("metadata", "Metadata"),
    ("title", "Title"),
    ("salutation", "Salutation"),
    ("opening", "Opening"),
    ("logistics", "Logistics"),
    ("compensation", "Compensation"),
    ("legal", "Legal"),
    ("closing", "Closing"),
    ("signature", "Signature"),
    ("footer", "Footer"),
]


def next_template_copy_name(source_name: str, existing_names: set[str]) -> str:
    base_name = source_name.strip()
    if not base_name:
        base_name = "Untitled Template"

    match = re.fullmatch(r"(.+?) \((\d+)\)", base_name)
    root_name = match.group(1) if match else base_name
    suffix = 1
    while True:
        candidate = f"{root_name} ({suffix})"
        if candidate not in existing_names:
            return candidate
        suffix += 1


def unique_template_name(requested_name: str, existing_names: set[str]) -> str:
    clean_name = requested_name.strip()
    if clean_name in existing_names:
        return next_template_copy_name(clean_name, existing_names)
    return clean_name


def _stage_summary(stage: PipelineStage | None) -> OfferStageSummaryRead | None:
    if stage is None:
        return None
    return OfferStageSummaryRead(
        id=stage.id,
        name=stage.name,
        slug=stage.slug,
        stageType=stage.stageType.value,
        order=stage.order,
    )


def _job_summary(job: JobPosting) -> OfferJobPostingSummaryRead:
    return OfferJobPostingSummaryRead(
        id=job.id,
        slug=job.slug,
        title=job.title,
        requisitionId=job.requisitionId,
    )


def _candidate_summary(candidate: Candidate | None) -> OfferCandidateSummaryRead | None:
    if candidate is None:
        return None
    return OfferCandidateSummaryRead(
        id=candidate.id,
        firstName=candidate.firstName or "",
        lastName=candidate.lastName or "",
        email=candidate.email or None,
        resumeUrl=candidate.resumeUrl,
    )


def _offer_read(offer: OfferLetter | None) -> OfferLetterRead | None:
    if offer is None:
        return None
    return OfferLetterRead.model_validate(offer)


def _template_list_item(template: OfferTemplate) -> OfferTemplateListItemRead:
    return OfferTemplateListItemRead(
        **OfferTemplateSummaryRead.model_validate(template).model_dump(),
        categoryNames=[category.name for category in template.categories or []],
    )


def _template_read(template: OfferTemplate) -> OfferTemplateRead:
    categories = sorted(template.categories or [], key=lambda item: item.order)
    sections = sorted(template.sections or [], key=lambda item: item.order)
    return OfferTemplateRead(
        **OfferTemplateSummaryRead.model_validate(template).model_dump(),
        footerHtml=template.footerHtml,
        websiteUrl=template.websiteUrl,
        createdByMemberId=template.createdByMemberId,
        updatedByMemberId=template.updatedByMemberId,
        categories=[OfferTemplateCategoryRead.model_validate(category) for category in categories],
        sections=[OfferTemplateSectionRead.model_validate(section) for section in sections],
    )


async def _resolve_offer_stage(
    repository: OfferRepository,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
) -> tuple[JobPosting, PipelineStage, list[PipelineStage]]:
    job = await repository.get_job_by_slug(organization_id, job_slug)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    stages = await repository.list_stages_for_job(organization_id, job.id)
    if stage_slug == "offer":
        stage = next((item for item in stages if item.stageType == StageType.OFFER), None)
    else:
        stage = next((item for item in stages if item.slug == stage_slug), None)

    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if stage.jobPostingId != job.id:
        raise HTTPException(status_code=400, detail="Stage does not belong to this job")
    if stage.stageType != StageType.OFFER:
        raise HTTPException(status_code=409, detail="Only offer stages have an offer workspace")
    return job, stage, stages


def _template_contains_compensation_tokens(template: OfferTemplate, category_id: str) -> bool:
    values = [template.footerHtml or ""]
    values.extend(
        section.html or ""
        for section in template.sections or []
        if section.categoryId == category_id
    )
    tokens = {
        match.group(1)
        for value in values
        for match in VARIABLE_PATTERN.finditer(value)
    }
    return bool(tokens & COMPENSATION_VARIABLE_TOKENS)


def _job_has_salary_data(requisition: JobRequisition | None) -> bool:
    return bool(
        requisition is not None
        and requisition.salaryMin is not None
        and requisition.salaryMax is not None
        and (requisition.currency or "").strip()
    )


def _format_compensation_preview_amount(value: float | int | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{float(value):,.2f}"


def _job_compensation_preview(requisition: JobRequisition | None) -> OfferJobCompensationPreviewRead | None:
    if not _job_has_salary_data(requisition) or requisition is None:
        return None
    return OfferJobCompensationPreviewRead(
        salaryMin=_format_compensation_preview_amount(requisition.salaryMin),
        salaryMax=_format_compensation_preview_amount(requisition.salaryMax),
        currency=(requisition.currency or "").strip(),
    )


def _candidate_eligibility(
    application: CandidateApplication,
    latest_offer: OfferLetter | None,
    *,
    requires_compensation: bool,
    job_has_salary_data: bool,
    require_email: bool = True,
) -> OfferEligibilityRead:
    candidate = application.candidate
    errors: list[str] = []
    warnings: list[str] = []
    if require_email and (candidate is None or not (candidate.email or "").strip()):
        errors.append("Candidate email is missing")
    if candidate is None or not (candidate.firstName or "").strip():
        errors.append("Candidate first name is missing")
    if candidate is None or not (candidate.lastName or "").strip():
        errors.append("Candidate last name is missing")
    if requires_compensation and not job_has_salary_data:
        errors.append("Job salary data is missing")
    return OfferEligibilityRead(canSend=not errors, errors=errors, warnings=warnings)


def _offer_status(latest_offer: OfferLetter | None) -> str:
    if latest_offer is None:
        return "UNSENT"
    if latest_offer.emailError:
        return "FAILED"
    return latest_offer.status.value


def _batch_status_for_counts(success_count: int, failure_count: int) -> OfferDispatchBatchStatus:
    if success_count > 0 and failure_count == 0:
        return OfferDispatchBatchStatus.COMPLETED
    if success_count > 0:
        return OfferDispatchBatchStatus.PARTIAL_FAILED
    return OfferDispatchBatchStatus.FAILED


def _candidate_validation_result(
    application: CandidateApplication,
    eligibility: OfferEligibilityRead,
) -> OfferCandidateValidationResultRead:
    return OfferCandidateValidationResultRead(
        applicationId=application.id,
        candidate=_candidate_summary(application.candidate),
        eligibility=eligibility,
    )


def _template_snapshot(
    template: OfferTemplate,
    category: OfferTemplateCategory,
) -> dict[str, Any]:
    return {
        "template": {
            "id": template.id,
            "name": template.name,
            "description": template.description,
            "logoUrl": template.logoUrl,
            "signatureUrl": template.signatureUrl,
            "signatoryName": template.signatoryName,
            "signatoryTitle": template.signatoryTitle,
            "footerHtml": template.footerHtml,
            "websiteUrl": template.websiteUrl,
        },
        "category": {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
        },
        "sections": [
            {
                "sectionKey": section.sectionKey,
                "sectionName": section.sectionName,
                "order": section.order,
                "tiptapJson": section.tiptapJson,
                "html": section.html,
            }
            for section in sorted(template.sections or [], key=lambda item: item.order)
            if section.categoryId == category.id
        ],
    }


def _split_candidate_display_name(display_name: str) -> tuple[str, str]:
    parts = " ".join(display_name.split()).split(" ", 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""
    return first_name, last_name


def _snapshot_with_candidate_name_override(
    snapshot: dict[str, Any],
    display_name: str | None,
) -> dict[str, Any]:
    if not display_name:
        return snapshot
    first_name, last_name = _split_candidate_display_name(display_name)
    next_snapshot = deepcopy(snapshot)
    next_snapshot["candidateNameOverride"] = {
        "displayName": display_name,
        "firstName": first_name,
        "lastName": last_name,
    }
    return next_snapshot


async def _get_template_and_category(
    repository: OfferRepository,
    organization_id: str,
    template_id: str,
    category_id: str,
) -> tuple[OfferTemplate, OfferTemplateCategory]:
    template = await repository.get_template_detail(organization_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    category = next((item for item in template.categories or [] if item.id == category_id), None)
    if category is None:
        raise HTTPException(status_code=404, detail="Offer template category not found")
    return template, category


async def get_workspace(
    db: AsyncSession,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
) -> OfferStageWorkspaceRead:
    repository = OfferRepository(db)
    job, stage, stages = await _resolve_offer_stage(repository, organization_id, job_slug, stage_slug)
    applications = await repository.list_applications_for_stage(organization_id, stage.id)
    latest_offers = await repository.list_latest_offers_for_applications(
        organization_id,
        [application.id for application in applications],
    )
    templates = await repository.list_templates(organization_id)
    recent_template = templates[0] if templates else None
    accepted_stage = next((item for item in stages if item.stageType == StageType.HIRED), None)
    rejected_stage = next((item for item in stages if item.stageType == StageType.REJECTED), None)
    job_has_salary_data = _job_has_salary_data(job.requisition)
    latest_batch = await repository.get_latest_batch_for_stage(organization_id, job.id, stage.id)

    rows = []
    for application in applications:
        latest_offer = latest_offers.get(application.id)
        eligibility = _candidate_eligibility(
            application,
            latest_offer,
            requires_compensation=False,
            job_has_salary_data=job_has_salary_data,
        )
        rows.append(
            {
                "applicationId": application.id,
                "candidate": _candidate_summary(application.candidate),
                "appliedAt": application.appliedAt,
                "source": application.source.value,
                "offerStatus": _offer_status(latest_offer),
                "latestOffer": _offer_read(latest_offer),
                "eligibility": eligibility,
            }
        )

    return OfferStageWorkspaceRead(
        stage=_stage_summary(stage),
        jobPosting=_job_summary(job),
        candidateCount=len(rows),
        candidates=rows,
        templates=[_template_list_item(template) for template in templates],
        recentTemplate=_template_list_item(recent_template) if recent_template is not None else None,
        latestBatch=OfferDispatchBatchRead.model_validate(latest_batch) if latest_batch else None,
        acceptedStage=_stage_summary(accepted_stage),
        rejectedStage=_stage_summary(rejected_stage),
        jobHasSalaryData=job_has_salary_data,
        jobCompensationPreview=_job_compensation_preview(job.requisition),
    )


async def list_templates(
    db: AsyncSession,
    organization_id: str,
    search: str | None = None,
    status: str | None = None,
) -> list[OfferTemplateListItemRead]:
    repository = OfferRepository(db)
    if status is not None and status not in {item.value for item in OfferTemplateStatus}:
        raise HTTPException(status_code=400, detail="Invalid template status")
    templates = await repository.list_templates(organization_id, search=search, status=status)
    return [_template_list_item(template) for template in templates]


def _category_slug(name: str, used: set[str]) -> str:
    return generate_unique_slug(name, used, fallback="category")


async def _create_default_sections(
    repository: OfferRepository,
    organization_id: str,
    template_id: str,
    category_id: str,
) -> None:
    await repository.add_all(
        [
            OfferTemplateSection(
                organizationId=organization_id,
                templateId=template_id,
                categoryId=category_id,
                sectionKey=section_key,
                sectionName=section_name,
                order=index,
                tiptapJson={},
                html="",
            )
            for index, (section_key, section_name) in enumerate(DEFAULT_SECTION_DEFINITIONS, start=1)
        ]
    )


async def create_template(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    body: OfferTemplateCreateRequest,
) -> OfferTemplateRead:
    repository = OfferRepository(db)
    requested_name = body.name.strip()
    existing_names = await repository.list_template_names(organization_id)
    template_name = unique_template_name(requested_name, existing_names)
    template = OfferTemplate(
        organizationId=organization_id,
        name=template_name,
        description=body.description,
        status=OfferTemplateStatus(body.status),
        logoUrl=body.logoUrl,
        signatureUrl=body.signatureUrl,
        signatoryName=body.signatoryName,
        signatoryTitle=body.signatoryTitle,
        footerHtml=body.footerHtml,
        websiteUrl=body.websiteUrl,
        createdByMemberId=actor_member_id,
        updatedByMemberId=actor_member_id,
    )
    await repository.add(template)
    category_inputs = body.categories or [OfferTemplateCategoryInput(name="General")]
    used_slugs: set[str] = set()
    categories: list[OfferTemplateCategory] = []
    for index, category_input in enumerate(category_inputs, start=1):
        slug = category_input.slug or _category_slug(category_input.name, used_slugs)
        if category_input.slug:
            used_slugs.add(slug)
        category = OfferTemplateCategory(
            organizationId=organization_id,
            templateId=template.id,
            name=category_input.name,
            slug=slug,
            order=category_input.order or index,
        )
        await repository.add(category)
        categories.append(category)
        await _create_default_sections(repository, organization_id, template.id, category.id)
    await db.commit()
    refreshed = await repository.get_template_detail(organization_id, template.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    return _template_read(refreshed)


async def get_template(
    db: AsyncSession,
    organization_id: str,
    template_id: str,
) -> OfferTemplateRead:
    repository = OfferRepository(db)
    template = await repository.get_template_detail(organization_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    return _template_read(template)


async def update_template(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    template_id: str,
    body: OfferTemplateUpdateRequest,
) -> OfferTemplateRead:
    repository = OfferRepository(db)
    template = await repository.get_template_detail(organization_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    for field_name in body.model_fields_set:
        value = getattr(body, field_name)
        if field_name == "status" and value is not None:
            value = OfferTemplateStatus(value)
        setattr(template, field_name, value)
    template.updatedByMemberId = actor_member_id
    await repository.add(template)
    await db.commit()
    refreshed = await repository.get_template_detail(organization_id, template_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    return _template_read(refreshed)


async def delete_template(
    db: AsyncSession,
    organization_id: str,
    template_id: str,
) -> None:
    repository = OfferRepository(db)
    template = await repository.get_template_detail(organization_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    if await repository.template_has_in_progress_batch(organization_id, template_id):
        raise HTTPException(status_code=409, detail="Template is referenced by an in-progress batch")
    await repository.delete(template)
    await db.commit()


async def copy_template(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    template_id: str,
    body: OfferTemplateCopyRequest,
) -> OfferTemplateRead:
    repository = OfferRepository(db)
    source = await repository.get_template_detail(organization_id, template_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    existing_names = await repository.list_template_names(organization_id)
    copied_name = unique_template_name(body.name, existing_names) if body.name else next_template_copy_name(source.name, existing_names)
    copy = OfferTemplate(
        organizationId=organization_id,
        name=copied_name,
        description=source.description,
        status=source.status,
        logoUrl=source.logoUrl,
        signatureUrl=source.signatureUrl,
        signatoryName=source.signatoryName,
        signatoryTitle=source.signatoryTitle,
        footerHtml=source.footerHtml,
        websiteUrl=source.websiteUrl,
        lastUsedAt=None,
        createdByMemberId=actor_member_id,
        updatedByMemberId=actor_member_id,
    )
    await repository.add(copy)
    category_id_map: dict[str, str] = {}
    for category in sorted(source.categories or [], key=lambda item: item.order):
        copied_category = OfferTemplateCategory(
            organizationId=organization_id,
            templateId=copy.id,
            name=category.name,
            slug=category.slug,
            order=category.order,
        )
        await repository.add(copied_category)
        category_id_map[category.id] = copied_category.id
    await repository.add_all(
        [
            OfferTemplateSection(
                organizationId=organization_id,
                templateId=copy.id,
                categoryId=category_id_map[section.categoryId],
                sectionKey=section.sectionKey,
                sectionName=section.sectionName,
                order=section.order,
                tiptapJson=section.tiptapJson,
                html=section.html,
            )
            for section in sorted(source.sections or [], key=lambda item: item.order)
            if section.categoryId in category_id_map
        ]
    )
    await db.commit()
    refreshed = await repository.get_template_detail(organization_id, copy.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    return _template_read(refreshed)


async def create_category(
    db: AsyncSession,
    organization_id: str,
    template_id: str,
    body: OfferTemplateCategoryCreateRequest,
) -> OfferTemplateCategoryRead:
    repository = OfferRepository(db)
    template = await repository.get_template_detail(organization_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Offer template not found")
    used_slugs = {category.slug for category in template.categories or []}
    slug = body.slug or _category_slug(body.name, used_slugs)
    category = OfferTemplateCategory(
        organizationId=organization_id,
        templateId=template_id,
        name=body.name,
        slug=slug,
        order=body.order or (len(template.categories or []) + 1),
    )
    await repository.add(category)
    await _create_default_sections(repository, organization_id, template_id, category.id)
    await db.commit()
    await db.refresh(category)
    return OfferTemplateCategoryRead.model_validate(category)


async def upsert_section(
    db: AsyncSession,
    organization_id: str,
    template_id: str,
    category_id: str,
    section_key: str,
    body: OfferTemplateSectionUpsertRequest,
) -> OfferTemplateSectionRead:
    repository = OfferRepository(db)
    category = await repository.get_category(organization_id, template_id, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Offer template category not found")
    if body.sectionKey is not None and body.sectionKey != section_key:
        raise HTTPException(status_code=400, detail="Section key mismatch")
    sanitized_html = validate_offer_variables(sanitize_offer_html(body.html)) or ""
    section = await repository.get_section(organization_id, template_id, category_id, section_key)
    if section is None:
        section = OfferTemplateSection(
            organizationId=organization_id,
            templateId=template_id,
            categoryId=category_id,
            sectionKey=section_key,
            sectionName=body.sectionName,
            order=body.order,
            tiptapJson=body.tiptapJson,
            html=sanitized_html,
        )
    else:
        section.sectionName = body.sectionName
        section.order = body.order
        section.tiptapJson = body.tiptapJson
        section.html = sanitized_html
    await repository.add(section)
    await db.commit()
    await db.refresh(section)
    return OfferTemplateSectionRead.model_validate(section)


async def validate_candidates(
    db: AsyncSession,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
    body: OfferCandidateValidationRequest,
) -> OfferCandidateValidationResponse:
    repository = OfferRepository(db)
    job, stage, _stages = await _resolve_offer_stage(repository, organization_id, job_slug, stage_slug)
    template, _category = await _get_template_and_category(
        repository,
        organization_id,
        body.templateId,
        body.categoryId,
    )
    applications = await repository.list_applications_by_ids(organization_id, body.applicationIds)
    by_id = {application.id: application for application in applications}
    latest_offers = await repository.list_latest_offers_for_applications(organization_id, body.applicationIds)
    requires_compensation = _template_contains_compensation_tokens(template, body.categoryId)
    job_has_salary_data = _job_has_salary_data(job.requisition)

    valid: list[OfferCandidateValidationResultRead] = []
    blocked: list[OfferCandidateValidationResultRead] = []
    warnings: list[str] = []
    for application_id in body.applicationIds:
        application = by_id.get(application_id)
        if application is None:
            blocked.append(
                OfferCandidateValidationResultRead(
                    applicationId=application_id,
                    candidate=None,
                    eligibility=OfferEligibilityRead(
                        canSend=False,
                        errors=["Application not found"],
                    ),
                )
            )
            continue
        if application.pipelineStageId != stage.id:
            blocked.append(
                OfferCandidateValidationResultRead(
                    applicationId=application.id,
                    candidate=_candidate_summary(application.candidate),
                    eligibility=OfferEligibilityRead(
                        canSend=False,
                        errors=["Application is not in this offer stage"],
                    ),
                )
            )
            continue
        eligibility = _candidate_eligibility(
            application,
            latest_offers.get(application.id),
            requires_compensation=requires_compensation,
            job_has_salary_data=job_has_salary_data,
        )
        result = _candidate_validation_result(application, eligibility)
        warnings.extend(eligibility.warnings)
        if eligibility.canSend:
            valid.append(result)
        else:
            blocked.append(result)
    return OfferCandidateValidationResponse(
        validCandidates=valid,
        blockedCandidates=blocked,
        warnings=sorted(set(warnings)),
    )


async def validate_download_candidates(
    db: AsyncSession,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
    body: OfferCandidateValidationRequest,
) -> OfferCandidateValidationResponse:
    repository = OfferRepository(db)
    job, stage, _stages = await _resolve_offer_stage(repository, organization_id, job_slug, stage_slug)
    template, _category = await _get_template_and_category(
        repository,
        organization_id,
        body.templateId,
        body.categoryId,
    )
    applications = await repository.list_applications_by_ids(organization_id, body.applicationIds)
    by_id = {application.id: application for application in applications}
    latest_offers = await repository.list_latest_offers_for_applications(organization_id, body.applicationIds)
    requires_compensation = _template_contains_compensation_tokens(template, body.categoryId)
    job_has_salary_data = _job_has_salary_data(job.requisition)

    valid: list[OfferCandidateValidationResultRead] = []
    blocked: list[OfferCandidateValidationResultRead] = []
    warnings: list[str] = []
    for application_id in body.applicationIds:
        application = by_id.get(application_id)
        if application is None:
            blocked.append(
                OfferCandidateValidationResultRead(
                    applicationId=application_id,
                    candidate=None,
                    eligibility=OfferEligibilityRead(
                        canSend=False,
                        errors=["Application not found"],
                    ),
                )
            )
            continue
        if application.pipelineStageId != stage.id:
            blocked.append(
                OfferCandidateValidationResultRead(
                    applicationId=application.id,
                    candidate=_candidate_summary(application.candidate),
                    eligibility=OfferEligibilityRead(
                        canSend=False,
                        errors=["Application is not in this offer stage"],
                    ),
                )
            )
            continue
        eligibility = _candidate_eligibility(
            application,
            latest_offers.get(application.id),
            requires_compensation=requires_compensation,
            job_has_salary_data=job_has_salary_data,
            require_email=False,
        )
        result = _candidate_validation_result(application, eligibility)
        warnings.extend(eligibility.warnings)
        if eligibility.canSend:
            valid.append(result)
        else:
            blocked.append(result)
    return OfferCandidateValidationResponse(
        validCandidates=valid,
        blockedCandidates=blocked,
        warnings=sorted(set(warnings)),
    )


async def generate_offer_download_archive(
    db: AsyncSession,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
    body: OfferDownloadCreateRequest,
) -> tuple[str, bytes]:
    repository = OfferRepository(db)
    job, stage, _stages = await _resolve_offer_stage(repository, organization_id, job_slug, stage_slug)
    template, category = await _get_template_and_category(
        repository,
        organization_id,
        body.templateId,
        body.categoryId,
    )
    validation = await validate_download_candidates(db, organization_id, job_slug, stage_slug, body)
    valid_ids = [item.applicationId for item in validation.validCandidates]
    if not valid_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No selected candidates can be downloaded",
                "blockedCandidates": [item.model_dump() for item in validation.blockedCandidates],
            },
        )

    applications = await repository.list_applications_by_ids(organization_id, valid_ids)
    by_id = {application.id: application for application in applications}
    ordered_applications = [by_id[application_id] for application_id in valid_ids if application_id in by_id]
    organization = job.organization or Organization(id=organization_id, name="Organization", slug="")
    snapshot = _template_snapshot(template, category)
    generated_at = datetime.now(UTC)
    archive_buffer = BytesIO()

    with ZipFile(archive_buffer, "w", compression=ZIP_DEFLATED) as archive:
        for index, application in enumerate(ordered_applications, start=1):
            candidate = application.candidate
            if candidate is None:
                continue
            candidate_name = f"{candidate.firstName} {candidate.lastName}".strip()
            offer_letter = _transient_offer_letter(
                organization_id=organization_id,
                application=application,
                template=template,
                category=category,
                stage=stage,
                job=job,
                expires_at=body.expiresAt,
                snapshot=snapshot,
            )
            html = render_offer_html(
                template_snapshot=snapshot,
                candidate=candidate,
                job_posting=job,
                offer_letter=offer_letter,
                organization=organization,
                generated_date=generated_at,
            )
            file_stem = safe_offer_file_stem(candidate_name, job.title)
            folder = f"{index:02d} - {_safe_archive_segment(candidate_name)}"
            if body.format == "pdf":
                archive.writestr(f"{folder}/{file_stem}.pdf", await render_offer_pdf(html))
            else:
                archive.writestr(f"{folder}/{file_stem}.docx", render_offer_docx(html, title=template.name))

    archive_name = f"{_safe_archive_segment(job.title)} offer letters {body.format}.zip"
    return archive_name, archive_buffer.getvalue()


def _transient_offer_letter(
    *,
    organization_id: str,
    application: CandidateApplication,
    template: OfferTemplate,
    category: OfferTemplateCategory,
    stage: PipelineStage,
    job: JobPosting,
    expires_at: datetime | None,
    snapshot: dict[str, Any],
) -> OfferLetter:
    return OfferLetter(
        id=f"download-{application.id}",
        organizationId=organization_id,
        applicationId=application.id,
        templateId=template.id,
        templateCategoryId=category.id,
        templateSnapshotJson=snapshot,
        stageId=stage.id,
        status=OfferStatus.DRAFT,
        title=template.name,
        message=None,
        expiresAt=expires_at,
        currency=job.requisition.currency if job.requisition is not None else "INR",
        salary=job.requisition.salaryMax if job.requisition is not None else None,
    )


def _safe_archive_segment(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value)
    return re.sub(r"\s+", " ", cleaned).strip()[:120] or "Offer Letter"


async def create_dispatch_batch(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    job_slug: str,
    stage_slug: str,
    body: OfferDispatchCreateRequest,
    background_tasks: BackgroundTasks,
) -> OfferDispatchCreateResponse:
    repository = OfferRepository(db)
    job, stage, _stages = await _resolve_offer_stage(repository, organization_id, job_slug, stage_slug)
    template, category = await _get_template_and_category(
        repository,
        organization_id,
        body.templateId,
        body.categoryId,
    )
    validation = await validate_candidates(db, organization_id, job_slug, stage_slug, body)
    valid_ids = [item.applicationId for item in validation.validCandidates]
    if not valid_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Some candidates cannot receive offers",
                "blockedCandidates": [item.model_dump() for item in validation.blockedCandidates],
            },
        )
    applications = await repository.list_applications_by_ids(organization_id, valid_ids)
    batch = OfferDispatchBatch(
        organizationId=organization_id,
        jobPostingId=job.id,
        stageId=stage.id,
        templateId=template.id,
        templateCategoryId=category.id,
        status=OfferDispatchBatchStatus.QUEUED,
        candidateCount=len(body.applicationIds),
        successCount=0,
        failureCount=len(validation.blockedCandidates),
        createdByMemberId=actor_member_id,
    )
    await repository.add(batch)
    await repository.withdraw_sent_offers_for_applications(organization_id, valid_ids)
    snapshot = _template_snapshot(template, category)
    name_overrides = {
        item.applicationId: item.displayName
        for item in body.candidateNameOverrides
        if item.applicationId in valid_ids
    }
    offer_letters = [
        OfferLetter(
            organizationId=organization_id,
            applicationId=application.id,
            batchId=batch.id,
            templateId=template.id,
            templateCategoryId=category.id,
            templateSnapshotJson=_snapshot_with_candidate_name_override(
                snapshot,
                name_overrides.get(application.id),
            ),
            stageId=stage.id,
            createdByMemberId=actor_member_id,
            status=OfferStatus.DRAFT,
            title=template.name,
            message=None,
            expiresAt=body.expiresAt,
            currency=job.requisition.currency if job.requisition is not None else "INR",
            salary=job.requisition.salaryMax if job.requisition is not None else None,
        )
        for application in applications
    ]
    await repository.add_all(offer_letters)
    template.lastUsedAt = datetime.now().astimezone()
    await repository.add(template)
    await db.commit()
    background_tasks.add_task(process_offer_dispatch_batch_task, organization_id, batch.id)
    return OfferDispatchCreateResponse(
        batch=OfferDispatchBatchRead.model_validate(batch),
        queuedOfferLetters=[OfferLetterRead.model_validate(offer) for offer in offer_letters],
        blockedCandidates=validation.blockedCandidates,
    )


async def get_dispatch_batch(
    db: AsyncSession,
    organization_id: str,
    batch_id: str,
) -> OfferDispatchBatchDetailRead:
    repository = OfferRepository(db)
    batch = await repository.get_batch_detail(organization_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Offer dispatch batch not found")
    return OfferDispatchBatchDetailRead(
        batch=OfferDispatchBatchRead.model_validate(batch),
        offerLetters=[OfferLetterRead.model_validate(offer) for offer in batch.offerLetters],
    )


async def get_application_offer_letters(
    db: AsyncSession,
    organization_id: str,
    application_id: str,
) -> OfferApplicationLettersRead:
    repository = OfferRepository(db)
    offers = await repository.list_offer_letters_for_application(organization_id, application_id)
    return OfferApplicationLettersRead(
        applicationId=application_id,
        offerLetters=[OfferLetterRead.model_validate(offer) for offer in offers],
    )


async def retry_failed_dispatch_batch(
    db: AsyncSession,
    organization_id: str,
    batch_id: str,
    background_tasks: BackgroundTasks,
) -> OfferDispatchBatchDetailRead:
    repository = OfferRepository(db)
    batch = await repository.get_batch_detail(organization_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Offer dispatch batch not found")
    reset_count = await repository.reset_failed_offers_for_batch(organization_id, batch_id)
    if reset_count == 0:
        raise HTTPException(status_code=400, detail="No failed offers are available to retry")
    batch.status = OfferDispatchBatchStatus.QUEUED
    batch.errorSummary = None
    batch.completedAt = None
    await repository.add(batch)
    await db.commit()
    background_tasks.add_task(process_offer_dispatch_batch_task, organization_id, batch_id)
    return await get_dispatch_batch(db, organization_id, batch_id)


async def process_offer_dispatch_batch_task(
    organization_id: str,
    batch_id: str,
) -> None:
    async with AsyncSessionLocal() as db:
        await process_offer_dispatch_batch(db, organization_id, batch_id)


async def process_offer_dispatch_batch(
    db: AsyncSession,
    organization_id: str,
    batch_id: str,
) -> None:
    repository = OfferRepository(db)
    batch = await repository.get_batch_detail(organization_id, batch_id)
    if batch is None:
        return
    if batch.status not in {OfferDispatchBatchStatus.QUEUED, OfferDispatchBatchStatus.PROCESSING}:
        return

    batch.status = OfferDispatchBatchStatus.PROCESSING
    batch.errorSummary = None
    await repository.add(batch)
    await db.commit()

    offers_to_process = [
        offer
        for offer in sorted(
            batch.offerLetters,
            key=lambda item: item.createdAt or datetime.min.replace(tzinfo=UTC),
        )
        if offer.status == OfferStatus.DRAFT
    ]
    for offer in offers_to_process:
        try:
            await _process_offer_letter(db, batch, offer)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            await _mark_offer_failed(organization_id, offer.id, str(exc))

    async with AsyncSessionLocal() as summary_db:
        summary_repository = OfferRepository(summary_db)
        summary_batch = await summary_repository.get_batch_detail(organization_id, batch_id)
        if summary_batch is None:
            return
        offers = summary_batch.offerLetters
        success_count = len([offer for offer in offers if offer.status == OfferStatus.SENT])
        row_failure_count = len(
            [
                offer
                for offer in offers
                if offer.status == OfferStatus.FAILED or bool(offer.emailError)
            ]
        )
        blocked_failure_count = max(summary_batch.candidateCount - len(offers), 0)
        failure_count = row_failure_count + blocked_failure_count
        summary_batch.successCount = success_count
        summary_batch.failureCount = failure_count
        summary_batch.completedAt = datetime.now(UTC)
        summary_batch.status = _batch_status_for_counts(success_count, failure_count)
        if summary_batch.status == OfferDispatchBatchStatus.COMPLETED:
            summary_batch.errorSummary = None
        elif summary_batch.status == OfferDispatchBatchStatus.PARTIAL_FAILED:
            summary_batch.errorSummary = f"{failure_count} offer(s) failed"
        else:
            summary_batch.errorSummary = "All offers failed"
        await summary_repository.add(summary_batch)
        await summary_db.commit()


async def _process_offer_letter(
    db: AsyncSession,
    batch: OfferDispatchBatch,
    offer: OfferLetter,
) -> None:
    application = offer.application
    candidate = application.candidate if application is not None else None
    job_posting = batch.jobPosting
    organization = batch.organization
    if application is None or candidate is None:
        raise OfferRenderError("Candidate application is missing")
    if job_posting is None:
        raise OfferRenderError("Job posting is missing")
    if organization is None:
        raise OfferRenderError("Organization is missing")
    if not (candidate.email or "").strip():
        raise OfferRenderError("Candidate email is missing")
    if not offer.templateSnapshotJson:
        raise OfferRenderError("Offer template snapshot is missing")

    now = datetime.now(UTC)
    html = render_offer_html(
        template_snapshot=offer.templateSnapshotJson,
        candidate=candidate,
        job_posting=job_posting,
        offer_letter=offer,
        organization=organization,
        generated_date=now,
    )
    pdf = await render_offer_pdf(html)
    candidate_name = f"{candidate.firstName} {candidate.lastName}".strip()
    file_name = safe_offer_file_name(candidate_name, job_posting.title)
    storage_path = offer_storage_path(
        organization_id=offer.organizationId,
        job_posting_id=batch.jobPostingId,
        application_id=offer.applicationId,
        offer_letter_id=offer.id,
        file_name=file_name,
    )
    token = offer.candidateToken or secrets.token_urlsafe(32)
    accept_url, reject_url = _offer_response_links(token)
    expires_at_text = _format_expiry(offer.expiresAt)
    settings = get_settings()
    upload = None
    try:
        upload = await upload_offer_pdf(pdf, storage_path)
    except RuntimeError:
        if settings.mode.strip().lower() == "production":
            raise

    offer.renderedHtml = html
    offer.pdfUrl = upload.public_url if upload else None
    offer.storageBucket = upload.bucket if upload else None
    offer.storagePath = upload.path if upload else None
    offer.fileName = file_name
    offer.candidateToken = token
    offer.emailError = None
    db.add(offer)
    await db.flush()
    await db.commit()

    await ResendEmailService().send_offer_letter(
        to_email=candidate.email,
        candidate_name=candidate_name,
        job_title=job_posting.title,
        organization_name=organization.name,
        download_url=upload.public_url if upload else None,
        attachment_pdf=None if upload else pdf,
        attachment_filename=None if upload else file_name,
        accept_url=accept_url,
        reject_url=reject_url,
        expires_at_text=expires_at_text,
    )

    offer.status = OfferStatus.SENT
    offer.sentAt = now
    offer.emailSentAt = now
    offer.emailError = None
    db.add(offer)
    await db.flush()


async def _mark_offer_failed(
    organization_id: str,
    offer_id: str,
    error: str,
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OfferLetter).where(
                OfferLetter.organizationId == organization_id,
                OfferLetter.id == offer_id,
            )
        )
        offer = result.scalar_one_or_none()
        if offer is None:
            return
        offer.status = OfferStatus.FAILED
        offer.emailError = error[:2000]
        db.add(offer)
        await db.commit()


def _offer_response_links(token: str) -> tuple[str, str]:
    base_url = get_settings().public_app_url.rstrip("/")
    # Direct GET links are product-requested for Phase 6. Email security scanners may prefetch them.
    return (
        f"{base_url}/public/offers/{token}/accept",
        f"{base_url}/public/offers/{token}/reject",
    )


def _format_expiry(value: datetime | None) -> str:
    if value is None:
        return "the expiry date provided by the hiring team"
    return value.astimezone().strftime("%d %b %Y")


async def accept_offer_by_token(db: AsyncSession, token: str) -> str:
    return await _respond_to_offer_by_token(
        db,
        token,
        accepted=True,
        target_stage_type=StageType.HIRED,
        response_status=OfferStatus.ACCEPTED,
        response_message="Offer accepted",
        history_note="Offer accepted by candidate",
    )


async def reject_offer_by_token(db: AsyncSession, token: str) -> str:
    return await _respond_to_offer_by_token(
        db,
        token,
        accepted=False,
        target_stage_type=StageType.REJECTED,
        response_status=OfferStatus.REJECTED,
        response_message="Offer rejected",
        history_note="Offer rejected by candidate",
    )


async def get_offer_download_url_by_token(db: AsyncSession, token: str) -> str:
    repository = OfferRepository(db)
    offer = await repository.get_offer_by_token(token)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    if offer.status == OfferStatus.WITHDRAWN:
        raise HTTPException(status_code=410, detail="This offer is no longer active")
    if not offer.pdfUrl:
        raise HTTPException(status_code=404, detail="Offer PDF is not available")
    return offer.pdfUrl


async def _respond_to_offer_by_token(
    db: AsyncSession,
    token: str,
    *,
    accepted: bool,
    target_stage_type: StageType,
    response_status: OfferStatus,
    response_message: str,
    history_note: str,
) -> str:
    repository = OfferRepository(db)
    offer = await repository.get_offer_by_token(token)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")

    if offer.status == response_status:
        return response_message
    opposite_status = OfferStatus.REJECTED if accepted else OfferStatus.ACCEPTED
    if offer.status == opposite_status:
        return "Offer already responded"
    if offer.status == OfferStatus.WITHDRAWN:
        return "This offer is no longer active"
    if offer.status == OfferStatus.EXPIRED:
        return "Offer expired"
    if offer.status not in {OfferStatus.SENT, OfferStatus.EXPIRED}:
        return "This offer is no longer active"

    latest_offer = await repository.get_latest_offer_for_application(
        offer.organizationId,
        offer.applicationId,
    )
    if latest_offer is None or latest_offer.id != offer.id:
        return "This offer is no longer active"

    now = datetime.now(UTC)
    if offer.expiresAt is not None and now > _as_aware_utc(offer.expiresAt):
        if offer.status == OfferStatus.SENT:
            offer.status = OfferStatus.EXPIRED
            offer.responseIgnoredAt = now
            db.add(offer)
            await db.commit()
        return "Offer expired"

    application = offer.application
    if application is None:
        raise HTTPException(status_code=404, detail="Candidate application not found")

    target_stage = await repository.get_first_stage_by_type(
        offer.organizationId,
        application.jobPostingId,
        target_stage_type,
    )
    if target_stage is not None:
        if target_stage.jobPostingId != application.jobPostingId:
            raise HTTPException(status_code=400, detail="Target stage does not belong to this job posting")
        if application.pipelineStageId != target_stage.id:
            from_stage_id = application.pipelineStageId
            application.pipelineStageId = target_stage.id
            db.add(application)
            await repository.add_stage_history(
                ApplicationStageHistory(
                    organizationId=offer.organizationId,
                    applicationId=application.id,
                    fromStageId=from_stage_id,
                    toStageId=target_stage.id,
                    movedByMemberId=None,
                    note=history_note,
                )
            )

    offer.status = response_status
    offer.respondedAt = now
    offer.emailError = None
    db.add(offer)
    await db.commit()
    return response_message


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
