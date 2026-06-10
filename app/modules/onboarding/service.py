from __future__ import annotations

import secrets
from datetime import UTC, datetime
from html import escape

import bcrypt
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.resend_service import ResendEmailService
from app.models.recruitment import (
    ApplicationStageHistory,
    CandidateApplication,
    OnboardingRecord,
    OnboardingStatus,
    PipelineStage,
    StageType,
)
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.schema import (
    AcceptedOnboardingCandidateRead,
    AcceptedOnboardingWorkspaceRead,
    OnboardingAssignCredentialsRequest,
    OnboardingAssignCredentialsResponse,
    OnboardingCandidateSummaryRead,
    OnboardingPublicRead,
    OnboardingRecordRead,
    OnboardingSendRequest,
    OnboardingSendResponse,
    OnboardingStageSummaryRead,
    OnboardingSubmitDocumentsRequest,
    OnboardingSubmitDocumentsResponse,
    OnboardWorkspaceCandidateRead,
    OnboardWorkspaceRead,
)
from app.modules.onboarding.storage import upload_onboarding_document
from app.shared.config import get_settings
from app.shared.database import AsyncSessionLocal


def _stage_summary(stage: PipelineStage | None) -> OnboardingStageSummaryRead | None:
    if stage is None:
        return None
    return OnboardingStageSummaryRead(
        id=stage.id,
        name=stage.name,
        slug=stage.slug,
        stageType=stage.stageType.value,
        order=stage.order,
    )


def _job_summary(job: object) -> object:
    from app.models.recruitment import JobPosting
    if not isinstance(job, JobPosting):
        return None
    from app.modules.onboarding.schema import OnboardingJobPostingSummaryRead
    return OnboardingJobPostingSummaryRead(
        id=job.id,
        slug=job.slug,
        title=job.title,
    )


def _candidate_summary(candidate: object) -> OnboardingCandidateSummaryRead | None:
    from app.models.recruitment import Candidate
    if not isinstance(candidate, Candidate):
        return None
    return OnboardingCandidateSummaryRead(
        id=candidate.id,
        firstName=candidate.firstName or "",
        lastName=candidate.lastName or "",
        email=candidate.email or None,
        resumeUrl=candidate.resumeUrl,
    )


def _onboarding_read(record: OnboardingRecord | None) -> OnboardingRecordRead | None:
    if record is None:
        return None
    return OnboardingRecordRead.model_validate(record)


def _onboarding_status(record: OnboardingRecord | None) -> str:
    if record is None:
        return "UNSENT"
    if record.credentialsEmailError:
        return "FAILED"
    return record.status.value


async def _resolve_stage(
    repository: OnboardingRepository,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
    expected_stage_type: StageType | None = None,
) -> tuple[object, PipelineStage, list[PipelineStage]]:
    from app.models.recruitment import JobPosting
    job = await repository.get_job_by_slug(organization_id, job_slug)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    stages = await repository.list_stages_for_job(organization_id, job.id)
    stage = next((item for item in stages if item.slug == stage_slug), None)

    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if stage.jobPostingId != job.id:
        raise HTTPException(status_code=400, detail="Stage does not belong to this job")
    if expected_stage_type is not None and stage.stageType != expected_stage_type:
        raise HTTPException(
            status_code=409,
            detail=f"This stage type does not have an onboarding workspace",
        )
    return job, stage, stages


async def get_accepted_workspace(
    db: AsyncSession,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
) -> AcceptedOnboardingWorkspaceRead:
    repository = OnboardingRepository(db)
    job, stage, stages = await _resolve_stage(
        repository, organization_id, job_slug, stage_slug,
        expected_stage_type=StageType.HIRED,
    )
    applications = await repository.list_applications_for_stage(organization_id, stage.id)
    application_ids = [app.id for app in applications]
    onboarding_records = await repository.list_onboarding_for_applications(organization_id, application_ids)
    onboard_stage = await repository.get_first_stage_by_type(organization_id, job.id, StageType.ONBOARDING)

    rows = []
    for application in applications:
        record = onboarding_records.get(application.id)
        rows.append(
            AcceptedOnboardingCandidateRead(
                applicationId=application.id,
                candidate=_candidate_summary(application.candidate),
                appliedAt=application.appliedAt,
                source=application.source.value,
                onboardingStatus=_onboarding_status(record),
                latestOnboarding=_onboarding_read(record),
            )
        )

    return AcceptedOnboardingWorkspaceRead(
        stage=_stage_summary(stage),
        jobPosting=_job_summary(job),
        candidateCount=len(rows),
        candidates=rows,
        onboardStage=_stage_summary(onboard_stage),
    )


async def send_document_requests(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    job_slug: str,
    stage_slug: str,
    body: OnboardingSendRequest,
    background_tasks: BackgroundTasks,
) -> OnboardingSendResponse:
    repository = OnboardingRepository(db)
    job, stage, _stages = await _resolve_stage(
        repository, organization_id, job_slug, stage_slug,
        expected_stage_type=StageType.HIRED,
    )
    if not body.applicationIds:
        raise HTTPException(status_code=400, detail="No candidates selected")

    applications = await repository.list_applications_by_ids(organization_id, body.applicationIds)
    if not applications:
        raise HTTPException(status_code=400, detail="No valid candidates found")

    existing = await repository.list_onboarding_for_applications(
        organization_id, body.applicationIds
    )
    records = []
    for application in applications:
        if application.id in existing:
            continue
        candidate = application.candidate
        if candidate is None or not (candidate.email or "").strip():
            continue
        if candidate is None or not (candidate.firstName or "").strip():
            continue
        if candidate is None or not (candidate.lastName or "").strip():
            continue

        token = secrets.token_urlsafe(32)
        record = OnboardingRecord(
            organizationId=organization_id,
            applicationId=application.id,
            candidateToken=token,
            status=OnboardingStatus.PENDING,
        )
        records.append(record)

    if not records:
        raise HTTPException(
            status_code=400,
            detail="All selected candidates already have ongoing onboarding or are invalid",
        )

    await repository.add_all(records)
    await db.commit()

    org_name = getattr(job, "organization", None)
    org_name_str = getattr(org_name, "name", "Company") if org_name else "Company"

    for record in records:
        background_tasks.add_task(
            _send_onboarding_email_task,
            organization_id,
            record.id,
            job.title,
            org_name_str,
        )

    return OnboardingSendResponse(requestedCount=len(records))


async def _send_onboarding_email_task(
    organization_id: str,
    record_id: str,
    job_title: str,
    organization_name: str,
) -> None:
    async with AsyncSessionLocal() as db:
        repository = OnboardingRepository(db)
        result = await db.execute(
            __import__("sqlalchemy").select(OnboardingRecord)
            .options(
                __import__("sqlalchemy").orm.joinedload(OnboardingRecord.application)
                .joinedload(CandidateApplication.candidate)
            )
            .where(
                OnboardingRecord.organizationId == organization_id,
                OnboardingRecord.id == record_id,
            )
        )
        record = result.unique().scalar_one_or_none()
        if record is None:
            return
        application = record.application
        candidate = application.candidate if application else None
        if candidate is None or not candidate.email:
            record.credentialsEmailError = "Candidate email is missing"
            db.add(record)
            await db.commit()
            return

        settings = get_settings()
        base_url = settings.public_app_url.rstrip("/")
        submission_url = f"{base_url}/document-submission/{record.candidateToken}"
        candidate_name = f"{candidate.firstName} {candidate.lastName}".strip()

        try:
            await ResendEmailService().send_onboarding_document_request(
                to_email=candidate.email,
                candidate_name=candidate_name,
                job_title=job_title,
                organization_name=organization_name,
                submission_url=submission_url,
            )
            record.tokenSentAt = datetime.now(UTC)
            record.credentialsEmailError = None
        except HTTPException as exc:
            record.credentialsEmailError = str(exc.detail)[:2000]
        except Exception as exc:
            record.credentialsEmailError = str(exc)[:2000]
        db.add(record)
        await db.commit()


async def get_onboard_workspace(
    db: AsyncSession,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
) -> OnboardWorkspaceRead:
    repository = OnboardingRepository(db)
    job, stage, stages = await _resolve_stage(
        repository, organization_id, job_slug, stage_slug,
        expected_stage_type=StageType.ONBOARDING,
    )
    applications = await repository.list_applications_for_stage(organization_id, stage.id)
    application_ids = [app.id for app in applications]
    onboarding_records = await repository.list_onboarding_for_applications(organization_id, application_ids)

    rows = []
    for application in applications:
        record = onboarding_records.get(application.id)
        rows.append(
            OnboardWorkspaceCandidateRead(
                applicationId=application.id,
                candidate=_candidate_summary(application.candidate),
                appliedAt=application.appliedAt,
                source=application.source.value,
                onboardingStatus=_onboarding_status(record),
                onboardingRecordId=record.id if record else None,
                aadharUrl=record.aadharUrl if record else None,
                panUrl=record.panUrl if record else None,
                assignedRoleId=record.assignedRoleId if record else None,
                assignedEmail=record.assignedEmail if record else None,
                credentialsSentAt=record.credentialsSentAt if record else None,
                credentialsEmailError=record.credentialsEmailError if record else None,
            )
        )

    return OnboardWorkspaceRead(
        stage=_stage_summary(stage),
        jobPosting=_job_summary(job),
        candidateCount=len(rows),
        candidates=rows,
    )


async def assign_credentials(
    db: AsyncSession,
    organization_id: str,
    record_id: str,
    body: OnboardingAssignCredentialsRequest,
) -> OnboardingAssignCredentialsResponse:
    repository = OnboardingRepository(db)
    result = await db.execute(
        __import__("sqlalchemy").select(OnboardingRecord)
        .where(
            OnboardingRecord.organizationId == organization_id,
            OnboardingRecord.id == record_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Onboarding record not found")
    if record.status == OnboardingStatus.CREDENTIALS_SENT:
        raise HTTPException(
            status_code=400,
            detail="Credentials have already been sent",
        )

    record.assignedRoleId = body.roleId
    record.assignedEmail = body.email
    db.add(record)
    await db.commit()

    return OnboardingAssignCredentialsResponse(
        onboardingId=record.id,
        status=record.status.value,
    )


async def confirm_and_send_credentials(
    db: AsyncSession,
    organization_id: str,
    record_id: str,
) -> dict[str, str]:
    repository = OnboardingRepository(db)
    result = await db.execute(
        __import__("sqlalchemy").select(OnboardingRecord)
        .options(
            __import__("sqlalchemy").orm.joinedload(OnboardingRecord.application)
            .joinedload(CandidateApplication.candidate)
        )
        .where(
            OnboardingRecord.organizationId == organization_id,
            OnboardingRecord.id == record_id,
        )
    )
    record = result.unique().scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Onboarding record not found")

    application = record.application
    candidate = application.candidate if application else None
    if candidate is None or not candidate.email:
        raise HTTPException(status_code=400, detail="Candidate email is missing")
    if not record.assignedEmail:
        raise HTTPException(status_code=400, detail="Assigned email not set")

    settings = get_settings()
    login_url = f"{settings.public_app_url.rstrip('/')}/login"
    candidate_name = f"{candidate.firstName} {candidate.lastName}".strip()

    try:
        await ResendEmailService().send_onboarding_credentials(
            to_email=record.assignedEmail,
            candidate_name=candidate_name,
            login_email=record.assignedEmail,
            login_url=login_url,
        )
        record.credentialsSentAt = datetime.now(UTC)
        record.status = OnboardingStatus.CREDENTIALS_SENT
        record.credentialsEmailError = None
    except HTTPException as exc:
        record.credentialsEmailError = str(exc.detail)[:2000]
    except Exception as exc:
        record.credentialsEmailError = str(exc)[:2000]

    db.add(record)
    await db.commit()

    return {
        "status": record.status.value,
        "email": record.assignedEmail,
    }


async def get_public_onboarding(
    db: AsyncSession,
    token: str,
) -> OnboardingPublicRead:
    repository = OnboardingRepository(db)
    record = await repository.get_onboarding_by_token(token)
    if record is None:
        raise HTTPException(status_code=404, detail="Onboarding request not found")

    application = record.application
    candidate = application.candidate if application else None
    job_posting = application.jobPosting if application else None
    if candidate is None or job_posting is None:
        raise HTTPException(status_code=404, detail="Onboarding data not found")

    org_name = "Company"
    if job_posting.organization:
        org_name = job_posting.organization.name or "Company"

    return OnboardingPublicRead(
        token=record.candidateToken,
        candidateName=f"{candidate.firstName or ''} {candidate.lastName or ''}".strip(),
        jobTitle=job_posting.title,
        organizationName=org_name,
        status=record.status.value,
        submittedAt=record.submittedAt,
    )


async def submit_documents(
    db: AsyncSession,
    token: str,
    body: OnboardingSubmitDocumentsRequest,
) -> OnboardingSubmitDocumentsResponse:
    repository = OnboardingRepository(db)
    record = await repository.get_onboarding_by_token(token)
    if record is None:
        raise HTTPException(status_code=404, detail="Onboarding request not found")
    if record.status != OnboardingStatus.PENDING:
        return OnboardingSubmitDocumentsResponse(
            status=record.status.value,
            message="Documents have already been submitted",
        )

    application = record.application
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    settings = get_settings()

    aadhar_path = f"{_safe_path_segment(record.organizationId)}/onboarding/{_safe_path_segment(application.id)}/{_safe_path_segment(record.id)}/aadhar.pdf"
    pan_path = f"{_safe_path_segment(record.organizationId)}/onboarding/{_safe_path_segment(application.id)}/{_safe_path_segment(record.id)}/pan.pdf"

    upload_success = True
    try:
        aadhar_upload = await upload_onboarding_document(
            file_base64=body.aadharBase64,
            storage_path=aadhar_path,
            content_type="application/pdf",
        )
        record.aadharUrl = aadhar_upload.public_url
        record.aadharBucket = aadhar_upload.bucket
        record.aadharStoragePath = aadhar_upload.path
    except RuntimeError:
        if settings.mode.strip().lower() == "production":
            raise
        upload_success = False

    try:
        pan_upload = await upload_onboarding_document(
            file_base64=body.panBase64,
            storage_path=pan_path,
            content_type="application/pdf",
        )
        record.panUrl = pan_upload.public_url
        record.panBucket = pan_upload.bucket
        record.panStoragePath = pan_upload.path
    except RuntimeError:
        if settings.mode.strip().lower() == "production":
            raise
        upload_success = False

    if not upload_success and settings.mode.strip().lower() != "production":
        record.aadharUrl = record.aadharUrl or "mock://aadhar"
        record.panUrl = record.panUrl or "mock://pan"

    record.status = OnboardingStatus.DOCUMENTS_SUBMITTED
    record.submittedAt = datetime.now(UTC)
    db.add(record)

    onboard_stage = await repository.get_first_stage_by_type(
        record.organizationId,
        application.jobPostingId,
        StageType.ONBOARDING,
    )
    if onboard_stage is None:
        from app.models.recruitment import PipelineStage as Ps, generate_uuid
        onboard_stage = Ps(
            id=generate_uuid(),
            organizationId=record.organizationId,
            jobPostingId=application.jobPostingId,
            name="Onboard",
            slug="onboard",
            order=999.0,
            stageType=StageType.ONBOARDING,
            offerLetterEnabled=True,
            isFinal=True,
        )
        db.add(onboard_stage)
        await db.flush()

    if application.pipelineStageId != onboard_stage.id:
        from_stage_id = application.pipelineStageId
        application.pipelineStageId = onboard_stage.id
        db.add(application)
        history = ApplicationStageHistory(
            organizationId=record.organizationId,
            applicationId=application.id,
            fromStageId=from_stage_id,
            toStageId=onboard_stage.id,
            movedByMemberId=None,
            note="Documents submitted by candidate",
        )
        db.add(history)

    await db.commit()

    return OnboardingSubmitDocumentsResponse(
        status=record.status.value,
        message="Documents submitted successfully",
    )


async def confirm_assign_credentials(
    db: AsyncSession,
    organization_id: str,
    record_id: str,
) -> dict[str, str]:
    repository = OnboardingRepository(db)
    result = await db.execute(
        __import__("sqlalchemy").select(OnboardingRecord).where(
            OnboardingRecord.organizationId == organization_id,
            OnboardingRecord.id == record_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Onboarding record not found")

    password = _generate_password()

    record.credentialsEmailError = None
    db.add(record)
    await db.commit()

    return {
        "password": password,
        "email": record.assignedEmail or "",
        "candidateName": "",
    }


async def confirm_and_send_credentials_with_password(
    db: AsyncSession,
    organization_id: str,
    record_id: str,
    password: str,
) -> dict[str, str]:
    repository = OnboardingRepository(db)
    result = await db.execute(
        __import__("sqlalchemy").select(OnboardingRecord)
        .options(
            __import__("sqlalchemy").orm.joinedload(OnboardingRecord.application)
            .joinedload(CandidateApplication.candidate)
        )
        .where(
            OnboardingRecord.organizationId == organization_id,
            OnboardingRecord.id == record_id,
        )
    )
    record = result.unique().scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Onboarding record not found")

    application = record.application
    candidate = application.candidate if application else None
    if candidate is None or not record.assignedEmail:
        raise HTTPException(status_code=400, detail="Candidate or email missing")

    settings = get_settings()
    login_url = f"{settings.public_app_url.rstrip('/')}/login"
    candidate_name = f"{candidate.firstName} {candidate.lastName}".strip()

    try:
        await ResendEmailService().send_onboarding_credentials(
            to_email=record.assignedEmail,
            candidate_name=candidate_name,
            login_email=record.assignedEmail,
            password=password,
            login_url=login_url,
        )
        record.credentialsSentAt = datetime.now(UTC)
        record.status = OnboardingStatus.CREDENTIALS_SENT
        record.credentialsEmailError = None
    except HTTPException as exc:
        record.credentialsEmailError = str(exc.detail)[:2000]
    except Exception as exc:
        record.credentialsEmailError = str(exc)[:2000]

    db.add(record)
    await db.commit()

    return {"status": record.status.value}


def _generate_password(length: int = 12) -> str:
    import string
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = "".join(secrets.choice(alphabet) for _ in range(length))
    if not any(c.islower() for c in password):
        password = password[:-1] + secrets.choice(string.ascii_lowercase)
    if not any(c.isupper() for c in password):
        password = password[:-1] + secrets.choice(string.ascii_uppercase)
    if not any(c.isdigit() for c in password):
        password = password[:-1] + secrets.choice(string.digits)
    return password


def _safe_path_segment(value: str) -> str:
    import re
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "", value).strip()
    return cleaned or "item"
