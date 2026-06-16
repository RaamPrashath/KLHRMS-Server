from __future__ import annotations

import base64
import binascii
import secrets
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.resend_service import ResendEmailService
from app.models.recruitment import (
    CandidateApplication,
    DocumentCollectionAllowedFormatGroup,
    DocumentCollectionField,
    DocumentCollectionFieldType,
    DocumentCollectionRequest,
    DocumentCollectionRequestStatus,
    DocumentCollectionTemplate,
    DocumentCollectionTemplateStatus,
    StageType,
)
from app.modules.document_collection.repository import DocumentCollectionRepository
from app.modules.document_collection.schema import (
    DocumentCollectionFieldInput,
    DocumentCollectionFieldRead,
    DocumentCollectionPublicRead,
    DocumentCollectionRequestDetailRead,
    DocumentCollectionRequestSummaryRead,
    DocumentCollectionSendRequest,
    DocumentCollectionSendResponse,
    DocumentCollectionSubmitRequest,
    DocumentCollectionSubmitResponse,
    DocumentCollectionTemplateCopyRequest,
    DocumentCollectionTemplateCreateRequest,
    DocumentCollectionTemplateListItemRead,
    DocumentCollectionTemplateRead,
    DocumentCollectionTemplateUpdateRequest,
)
from app.modules.onboarding.storage import upload_onboarding_document
from app.shared.config import get_settings
from app.shared.database import AsyncSessionLocal

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
FILE_EXTENSIONS = {"pdf", "doc", "docx"}
VIDEO_EXTENSIONS = {"mp4", "mov", "webm", "mkv"}


def _safe_path_segment(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in value.strip())
    return safe.strip(".-") or "file"


def _document_file_name(default_stem: str, file_name: str | None) -> str:
    safe_name = _safe_path_segment(file_name or default_stem)
    if "." not in PurePath(safe_name).name:
        return f"{safe_name}.bin"
    return safe_name


def _content_type(file_name: str, fallback: str | None = None) -> str:
    if fallback and "/" in fallback:
        return fallback
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension in {"jpg", "jpeg"}:
        return "image/jpeg"
    if extension == "png":
        return "image/png"
    if extension == "webp":
        return "image/webp"
    if extension == "gif":
        return "image/gif"
    if extension == "pdf":
        return "application/pdf"
    if extension == "doc":
        return "application/msword"
    if extension == "docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if extension == "mp4":
        return "video/mp4"
    if extension == "mov":
        return "video/quicktime"
    if extension == "webm":
        return "video/webm"
    return "application/octet-stream"


def _extension(file_name: str | None) -> str:
    if not file_name or "." not in file_name:
        return ""
    return file_name.rsplit(".", 1)[-1].lower()


def _matches_format_group(file_name: str | None, group: str) -> bool:
    if group == "ALL":
        return True
    extension = _extension(file_name)
    if group == "IMAGE":
        return extension in IMAGE_EXTENSIONS
    if group == "FILE":
        return extension in FILE_EXTENSIONS
    if group == "VIDEO":
        return extension in VIDEO_EXTENSIONS
    return False


def unique_template_name(requested_name: str, existing_names: set[str]) -> str:
    if requested_name not in existing_names:
        return requested_name
    index = 1
    while f"{requested_name} ({index})" in existing_names:
        index += 1
    return f"{requested_name} ({index})"


def next_copy_name(source_name: str, existing_names: set[str]) -> str:
    base = f"{source_name} - Copy"
    return unique_template_name(base, existing_names)


def _field_read(field: DocumentCollectionField) -> DocumentCollectionFieldRead:
    return DocumentCollectionFieldRead.model_validate(field)


def _template_read(template: DocumentCollectionTemplate) -> DocumentCollectionTemplateRead:
    return DocumentCollectionTemplateRead(
        id=template.id,
        organizationId=template.organizationId,
        name=template.name,
        description=template.description,
        status=template.status.value,
        lastUsedAt=template.lastUsedAt,
        createdByMemberId=template.createdByMemberId,
        updatedByMemberId=template.updatedByMemberId,
        createdAt=template.createdAt,
        updatedAt=template.updatedAt,
        fields=[_field_read(field) for field in sorted(template.fields or [], key=lambda item: item.order)],
    )


def _template_list_item(template: DocumentCollectionTemplate) -> DocumentCollectionTemplateListItemRead:
    return DocumentCollectionTemplateListItemRead(
        id=template.id,
        organizationId=template.organizationId,
        name=template.name,
        description=template.description,
        status=template.status.value,
        lastUsedAt=template.lastUsedAt,
        createdAt=template.createdAt,
        updatedAt=template.updatedAt,
        fieldCount=len(template.fields or []),
    )


def _request_summary(request: DocumentCollectionRequest | None) -> DocumentCollectionRequestSummaryRead | None:
    if request is None:
        return None
    snapshot = request.templateSnapshotJson or {}
    return DocumentCollectionRequestSummaryRead(
        id=request.id,
        templateId=request.templateId,
        templateName=str(snapshot.get("name") or "Document collection"),
        status=request.status.value,
        tokenSentAt=request.tokenSentAt,
        submittedAt=request.submittedAt,
        emailError=request.emailError,
        createdAt=request.createdAt,
    )


def _request_detail(request: DocumentCollectionRequest) -> DocumentCollectionRequestDetailRead:
    summary = _request_summary(request)
    if summary is None:
        raise HTTPException(status_code=404, detail="Document collection request not found")
    return DocumentCollectionRequestDetailRead(
        **summary.model_dump(),
        templateSnapshotJson=request.templateSnapshotJson or {},
        answersJson=request.answersJson,
    )


def _field_snapshot(field: DocumentCollectionField) -> dict[str, Any]:
    return {
        "id": field.id,
        "fieldType": field.fieldType.value,
        "name": field.name,
        "description": field.description,
        "required": field.required,
        "order": field.order,
        "allowedFormatGroup": field.allowedFormatGroup.value,
        "maxSizeBytes": field.maxSizeBytes,
    }


def _template_snapshot(template: DocumentCollectionTemplate) -> dict[str, Any]:
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "fields": [
            _field_snapshot(field)
            for field in sorted(template.fields or [], key=lambda item: item.order)
        ],
    }


def _ensure_publishable(template: DocumentCollectionTemplate) -> None:
    fields = list(template.fields or [])
    if not fields:
        raise HTTPException(status_code=400, detail="Add at least one field before publishing")
    if any(not field.name.strip() for field in fields):
        raise HTTPException(status_code=400, detail="Every field needs a name")


async def _replace_fields(
    repository: DocumentCollectionRepository,
    template: DocumentCollectionTemplate,
    organization_id: str,
    field_inputs: list[DocumentCollectionFieldInput],
) -> None:
    await repository.delete_fields_for_template(organization_id, template.id)
    for index, field_input in enumerate(field_inputs, start=1):
        await repository.add(
            DocumentCollectionField(
                organizationId=organization_id,
                templateId=template.id,
                fieldType=DocumentCollectionFieldType(field_input.fieldType),
                name=field_input.name,
                description=field_input.description,
                required=field_input.required,
                order=field_input.order or index,
                allowedFormatGroup=DocumentCollectionAllowedFormatGroup(field_input.allowedFormatGroup),
                maxSizeBytes=field_input.maxSizeBytes,
            )
        )


async def list_templates(
    db: AsyncSession,
    organization_id: str,
    search: str | None = None,
    status: str | None = None,
) -> list[DocumentCollectionTemplateListItemRead]:
    if status is not None and status not in {item.value for item in DocumentCollectionTemplateStatus}:
        raise HTTPException(status_code=400, detail="Invalid template status")
    repository = DocumentCollectionRepository(db)
    templates = await repository.list_templates(organization_id, search=search, status=status)
    return [_template_list_item(template) for template in templates]


async def create_template(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    body: DocumentCollectionTemplateCreateRequest,
) -> DocumentCollectionTemplateRead:
    repository = DocumentCollectionRepository(db)
    existing_names = await repository.list_template_names(organization_id)
    template = DocumentCollectionTemplate(
        organizationId=organization_id,
        name=unique_template_name(body.name, existing_names),
        description=body.description,
        status=DocumentCollectionTemplateStatus(body.status),
        createdByMemberId=actor_member_id,
        updatedByMemberId=actor_member_id,
    )
    await repository.add(template)
    default_fields = body.fields or [
        DocumentCollectionFieldInput(
            fieldType="FILE_UPLOAD",
            name="Document",
            required=True,
            allowedFormatGroup="ALL",
        )
    ]
    await _replace_fields(repository, template, organization_id, default_fields)
    refreshed = await repository.get_template_detail(organization_id, template.id)
    if refreshed is not None and refreshed.status == DocumentCollectionTemplateStatus.ACTIVE:
        _ensure_publishable(refreshed)
    await db.commit()
    refreshed = await repository.get_template_detail(organization_id, template.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Document collection template not found")
    return _template_read(refreshed)


async def get_template(
    db: AsyncSession,
    organization_id: str,
    template_id: str,
) -> DocumentCollectionTemplateRead:
    repository = DocumentCollectionRepository(db)
    template = await repository.get_template_detail(organization_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Document collection template not found")
    return _template_read(template)


async def get_request_detail(
    db: AsyncSession,
    organization_id: str,
    request_id: str,
) -> DocumentCollectionRequestDetailRead:
    repository = DocumentCollectionRepository(db)
    request = await repository.get_request_detail(organization_id, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Document collection request not found")
    return _request_detail(request)


async def update_template(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    template_id: str,
    body: DocumentCollectionTemplateUpdateRequest,
) -> DocumentCollectionTemplateRead:
    repository = DocumentCollectionRepository(db)
    template = await repository.get_template_detail(organization_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Document collection template not found")
    if body.name is not None:
        template.name = body.name
    if "description" in body.model_fields_set:
        template.description = body.description
    if body.status is not None:
        template.status = DocumentCollectionTemplateStatus(body.status)
    template.updatedByMemberId = actor_member_id
    await repository.add(template)
    if body.fields is not None:
        await _replace_fields(repository, template, organization_id, body.fields)
    refreshed = await repository.get_template_detail(organization_id, template_id)
    if refreshed is not None and refreshed.status == DocumentCollectionTemplateStatus.ACTIVE:
        _ensure_publishable(refreshed)
    await db.commit()
    refreshed = await repository.get_template_detail(organization_id, template_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Document collection template not found")
    return _template_read(refreshed)


async def delete_template(
    db: AsyncSession,
    organization_id: str,
    template_id: str,
) -> None:
    repository = DocumentCollectionRepository(db)
    template = await repository.get_template_detail(organization_id, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Document collection template not found")
    if await repository.template_has_pending_requests(organization_id, template_id):
        raise HTTPException(status_code=409, detail="Template is referenced by pending requests")
    await repository.delete(template)
    await db.commit()


async def copy_template(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    template_id: str,
    body: DocumentCollectionTemplateCopyRequest,
) -> DocumentCollectionTemplateRead:
    repository = DocumentCollectionRepository(db)
    source = await repository.get_template_detail(organization_id, template_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Document collection template not found")
    existing_names = await repository.list_template_names(organization_id)
    copy = DocumentCollectionTemplate(
        organizationId=organization_id,
        name=(body.name or next_copy_name(source.name, existing_names)).strip(),
        description=source.description,
        status=DocumentCollectionTemplateStatus.DRAFT,
        createdByMemberId=actor_member_id,
        updatedByMemberId=actor_member_id,
    )
    await repository.add(copy)
    await _replace_fields(
        repository,
        copy,
        organization_id,
        [
            DocumentCollectionFieldInput(
                fieldType=field.fieldType.value,
                name=field.name,
                description=field.description,
                required=field.required,
                order=field.order,
                allowedFormatGroup=field.allowedFormatGroup.value,
                maxSizeBytes=field.maxSizeBytes,
            )
            for field in sorted(source.fields or [], key=lambda item: item.order)
        ],
    )
    await db.commit()
    refreshed = await repository.get_template_detail(organization_id, copy.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Document collection template not found")
    return _template_read(refreshed)


async def _resolve_hired_stage(
    repository: DocumentCollectionRepository,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
) -> tuple[object, object]:
    job = await repository.get_job_by_slug(organization_id, job_slug)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    stage = await repository.get_stage_by_job_and_slug(organization_id, job.id, stage_slug)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if stage.stageType != StageType.HIRED:
        raise HTTPException(status_code=409, detail="This stage type does not have document collection")
    return job, stage


async def send_requests(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    job_slug: str,
    stage_slug: str,
    body: DocumentCollectionSendRequest,
    background_tasks: BackgroundTasks,
) -> DocumentCollectionSendResponse:
    repository = DocumentCollectionRepository(db)
    job, stage = await _resolve_hired_stage(repository, organization_id, job_slug, stage_slug)
    template = await repository.get_template_detail(organization_id, body.templateId)
    if template is None:
        raise HTTPException(status_code=404, detail="Document collection template not found")
    if template.status != DocumentCollectionTemplateStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Only published templates can be sent")
    _ensure_publishable(template)
    applications = await repository.list_applications_by_ids(organization_id, body.applicationIds)
    latest_requests = await repository.list_latest_requests_for_applications(organization_id, body.applicationIds)
    snapshot = _template_snapshot(template)
    records: list[DocumentCollectionRequest] = []
    for application in applications:
        if application.pipelineStageId != stage.id:
            continue
        latest = latest_requests.get(application.id)
        if latest and latest.status == DocumentCollectionRequestStatus.PENDING:
            continue
        candidate = application.candidate
        if candidate is None or not (candidate.email or "").strip():
            continue
        token = secrets.token_urlsafe(32)
        records.append(
            DocumentCollectionRequest(
                organizationId=organization_id,
                applicationId=application.id,
                templateId=template.id,
                candidateToken=token,
                status=DocumentCollectionRequestStatus.PENDING,
                templateSnapshotJson=snapshot,
                createdByMemberId=actor_member_id,
            )
        )
    if not records:
        raise HTTPException(status_code=400, detail="No selected candidates can receive document requests")
    await repository.add_all(records)
    template.lastUsedAt = datetime.now(UTC)
    await repository.add(template)
    await db.commit()

    org_name = getattr(getattr(job, "organization", None), "name", "Company") or "Company"
    for record in records:
        background_tasks.add_task(
            _send_document_collection_email_task,
            organization_id,
            record.id,
            getattr(job, "title", "Job"),
            org_name,
        )
    return DocumentCollectionSendResponse(requestedCount=len(records))


async def _send_document_collection_email_task(
    organization_id: str,
    request_id: str,
    job_title: str,
    organization_name: str,
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            __import__("sqlalchemy").select(DocumentCollectionRequest)
            .options(
                __import__("sqlalchemy").orm.joinedload(DocumentCollectionRequest.application)
                .joinedload(CandidateApplication.candidate)
            )
            .where(
                DocumentCollectionRequest.organizationId == organization_id,
                DocumentCollectionRequest.id == request_id,
            )
        )
        request = result.unique().scalar_one_or_none()
        if request is None:
            return
        application = request.application
        candidate = application.candidate if application else None
        if candidate is None or not candidate.email:
            request.status = DocumentCollectionRequestStatus.FAILED
            request.emailError = "Candidate email is missing"
            db.add(request)
            await db.commit()
            return

        settings = get_settings()
        base_url = settings.public_app_url.rstrip("/")
        submission_url = f"{base_url}/document-collection/{request.candidateToken}"
        candidate_name = f"{candidate.firstName or ''} {candidate.lastName or ''}".strip() or "Candidate"
        template_name = str((request.templateSnapshotJson or {}).get("name") or "Document collection")

        try:
            await ResendEmailService().send_document_collection_request(
                to_email=candidate.email,
                candidate_name=candidate_name,
                job_title=job_title,
                organization_name=organization_name,
                template_name=template_name,
                submission_url=submission_url,
            )
            now = datetime.now(UTC)
            request.tokenSentAt = now
            request.emailSentAt = now
            request.emailError = None
        except HTTPException as exc:
            request.status = DocumentCollectionRequestStatus.FAILED
            request.emailError = str(exc.detail)[:2000]
        except Exception as exc:
            request.status = DocumentCollectionRequestStatus.FAILED
            request.emailError = str(exc)[:2000]
        db.add(request)
        await db.commit()


async def get_public_request(db: AsyncSession, token: str) -> DocumentCollectionPublicRead:
    repository = DocumentCollectionRepository(db)
    request = await repository.get_request_by_token(token)
    if request is None:
        raise HTTPException(status_code=404, detail="Document collection request not found")
    application = request.application
    candidate = application.candidate if application else None
    job_posting = application.jobPosting if application else None
    if candidate is None or job_posting is None:
        raise HTTPException(status_code=404, detail="Document collection data not found")
    org_name = job_posting.organization.name if job_posting.organization else "Company"
    return DocumentCollectionPublicRead(
        token=request.candidateToken,
        candidateName=f"{candidate.firstName or ''} {candidate.lastName or ''}".strip(),
        jobTitle=job_posting.title,
        organizationName=org_name,
        status=request.status.value,
        submittedAt=request.submittedAt,
        template=request.templateSnapshotJson or {},
    )


def _answers_by_field(body: DocumentCollectionSubmitRequest) -> dict[str, Any]:
    return {answer.fieldId: answer for answer in body.answers}


async def submit_public_request(
    db: AsyncSession,
    token: str,
    body: DocumentCollectionSubmitRequest,
) -> DocumentCollectionSubmitResponse:
    repository = DocumentCollectionRepository(db)
    request = await repository.get_request_by_token(token)
    if request is None:
        raise HTTPException(status_code=404, detail="Document collection request not found")
    if request.status == DocumentCollectionRequestStatus.SUBMITTED:
        return DocumentCollectionSubmitResponse(status=request.status.value, message="Document collection already submitted")
    if request.status == DocumentCollectionRequestStatus.FAILED:
        request.status = DocumentCollectionRequestStatus.PENDING

    application = request.application
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    snapshot = request.templateSnapshotJson or {}
    fields = list(snapshot.get("fields") or [])
    answers_by_field = _answers_by_field(body)
    stored_answers: list[dict[str, Any]] = []

    for field in fields:
        field_id = str(field.get("id") or "")
        field_type = str(field.get("fieldType") or "SHORT_TEXT")
        field_name = str(field.get("name") or "Field")
        required = bool(field.get("required"))
        answer = answers_by_field.get(field_id)

        if field_type == "FILE_UPLOAD":
            if answer is None or not answer.fileBase64:
                if required:
                    raise HTTPException(status_code=422, detail=f"{field_name} is required")
                continue
            file_name = _document_file_name(field_id, answer.fileName)
            if not _matches_format_group(file_name, str(field.get("allowedFormatGroup") or "ALL")):
                raise HTTPException(status_code=422, detail=f"{field_name} has an unsupported file type")
            max_size = field.get("maxSizeBytes")
            if isinstance(max_size, int) and answer.fileSize is not None and answer.fileSize > max_size:
                raise HTTPException(status_code=422, detail=f"{field_name} exceeds the maximum file size")
            try:
                decoded = base64.b64decode(answer.fileBase64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise HTTPException(status_code=422, detail=f"{field_name} could not be read") from exc
            if isinstance(max_size, int) and len(decoded) > max_size:
                raise HTTPException(status_code=422, detail=f"{field_name} exceeds the maximum file size")
            storage_path = (
                f"{_safe_path_segment(request.organizationId)}/document-collection/"
                f"{_safe_path_segment(application.id)}/{_safe_path_segment(request.id)}/"
                f"{_safe_path_segment(field_id)}-{file_name}"
            )
            try:
                upload = await upload_onboarding_document(
                    file_base64=answer.fileBase64,
                    storage_path=storage_path,
                    content_type=_content_type(file_name, answer.fileType),
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=502, detail=f"Could not upload {field_name}. Please try again.") from exc
            stored_answers.append(
                {
                    "fieldId": field_id,
                    "fieldType": field_type,
                    "name": field_name,
                    "fileName": file_name,
                    "fileType": _content_type(file_name, answer.fileType),
                    "fileSize": len(decoded),
                    "url": upload.public_url,
                    "bucket": upload.bucket,
                    "path": upload.path,
                }
            )
            continue

        value = (answer.value if answer is not None else None) or ""
        if required and not value.strip():
            raise HTTPException(status_code=422, detail=f"{field_name} is required")
        if value.strip():
            stored_answers.append(
                {
                    "fieldId": field_id,
                    "fieldType": field_type,
                    "name": field_name,
                    "value": value.strip(),
                }
            )

    request.answersJson = {"answers": stored_answers}
    request.status = DocumentCollectionRequestStatus.SUBMITTED
    request.submittedAt = datetime.now(UTC)
    request.emailError = None
    db.add(request)
    await db.commit()
    return DocumentCollectionSubmitResponse(status=request.status.value, message="Document collection submitted successfully")


__all__ = [
    "_request_summary",
    "copy_template",
    "create_template",
    "delete_template",
    "get_public_request",
    "get_request_detail",
    "get_template",
    "list_templates",
    "send_requests",
    "submit_public_request",
    "update_template",
]
