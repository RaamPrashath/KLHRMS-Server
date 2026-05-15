from __future__ import annotations

from datetime import datetime, timezone
import re

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recruitment import (
    ApplicationSource,
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    EmploymentType,
    JobPosting,
    JobPostingStatus,
    JobRequisition,
    JobRequisitionStatus,
    PipelineStage,
    RequisitionApproval,
    RequisitionApprovalDecision,
    StageType,
)
from app.modules.jobs.repository import JobRequisitionRepository
from app.modules.jobs.schema import (
    JobRequisitionApprovalRead,
    JobRequisitionApprovalSummaryRead,
    JobRequisitionCreateRequest,
    JobRequisitionDecisionRequest,
    JobRequisitionDetailRead,
    JobRequisitionListItemRead,
    PublicJobApplicationRead,
    PublicJobApplicationRequest,
    PublicJobPostingDetailRead,
    PublicJobPostingListItemRead,
)


DEFAULT_PIPELINE_STAGES: list[dict[str, object]] = [
    {"name": "Applied", "order": 1.0, "color": None, "isDefault": True, "isFinal": False, "stageType": StageType.DEFAULT},
    {"name": "Screening", "order": 2.0, "color": None, "isDefault": True, "isFinal": False, "stageType": StageType.DEFAULT},
    {"name": "Interview Round 1", "order": 3.0, "color": None, "isDefault": True, "isFinal": False, "stageType": StageType.INTERVIEW},
    {"name": "Interview Round 2", "order": 4.0, "color": None, "isDefault": False, "isFinal": False, "stageType": StageType.INTERVIEW},
    {"name": "Offer", "order": 5.0, "color": None, "isDefault": True, "isFinal": False, "stageType": StageType.OFFER},
    {"name": "Hired", "order": 6.0, "color": None, "isDefault": True, "isFinal": True, "stageType": StageType.HIRED},
    {"name": "Rejected", "order": 7.0, "color": None, "isDefault": True, "isFinal": True, "stageType": StageType.REJECTED},
]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "item"


async def _generate_job_slug(
    repository: JobRequisitionRepository,
    organization_id: str,
    title: str,
) -> str:
    jobs = await repository.list_job_postings_for_org(organization_id)
    used = {job.slug for job in jobs if job.slug}
    base_slug = _slugify(title)
    candidate = base_slug
    suffix = 2
    while candidate in used:
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate


def _generate_stage_slug(name: str, used: set[str]) -> str:
    base_slug = _slugify(name)
    candidate = base_slug
    suffix = 2
    while candidate in used:
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _to_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _build_approval_summary(approvals: list[RequisitionApproval]) -> JobRequisitionApprovalSummaryRead:
    approved_count = sum(
        1 for approval in approvals if approval.decision == RequisitionApprovalDecision.APPROVED
    )
    rejected_count = sum(
        1 for approval in approvals if approval.decision == RequisitionApprovalDecision.REJECTED
    )
    pending_count = sum(
        1 for approval in approvals if approval.decision == RequisitionApprovalDecision.PENDING
    )
    return JobRequisitionApprovalSummaryRead(
        approvedCount=approved_count,
        rejectedCount=rejected_count,
        pendingCount=pending_count,
        totalCount=len(approvals),
    )


def _serialize_approval(approval: RequisitionApproval) -> JobRequisitionApprovalRead:
    approver_name = None
    if approval.approver is not None and approval.approver.user is not None:
        approver_name = approval.approver.user.name or approval.approver.user.email

    return JobRequisitionApprovalRead(
        id=approval.id,
        approverId=approval.approverId,
        approverName=approver_name,
        decision=approval.decision,
        comment=approval.comment,
        decidedAt=_to_utc_datetime(approval.decidedAt),
        createdAt=approval.createdAt,
    )


def _serialize_requisition(
    requisition: JobRequisition,
    actor_member_id: str,
) -> JobRequisitionListItemRead:
    approvals = requisition.approvals or []
    current_approval = next(
        (approval for approval in approvals if approval.approverId == actor_member_id),
        None,
    )
    raised_by_name = None
    if requisition.raisedBy is not None and requisition.raisedBy.user is not None:
        raised_by_name = requisition.raisedBy.user.name or requisition.raisedBy.user.email

    return JobRequisitionListItemRead(
        id=requisition.id,
        title=requisition.title,
        departmentId=requisition.departmentId,
        departmentName=requisition.department.name if requisition.department is not None else None,
        employmentType=requisition.employmentType,
        openings=requisition.openings,
        salaryMin=requisition.salaryMin,
        salaryMax=requisition.salaryMax,
        currency=requisition.currency,
        description=requisition.description,
        requirements=requisition.requirements,
        skills=list(requisition.skills or []),
        location=requisition.location,
        isRemote=requisition.isRemote,
        raisedById=requisition.raisedById,
        raisedByName=raised_by_name,
        targetDate=_to_utc_datetime(requisition.targetDate),
        status=requisition.status,
        createdAt=requisition.createdAt,
        updatedAt=requisition.updatedAt,
        closedAt=_to_utc_datetime(requisition.closedAt),
        approvalSummary=_build_approval_summary(approvals),
        currentUserApprovalDecision=current_approval.decision if current_approval is not None else None,
        currentUserCanApprove=(
            requisition.status == JobRequisitionStatus.PENDING
            and current_approval is not None
            and current_approval.decision == RequisitionApprovalDecision.PENDING
        ),
        canSubmit=(
            requisition.raisedById == actor_member_id
            and requisition.status == JobRequisitionStatus.DRAFT
        ),
        approvals=[_serialize_approval(approval) for approval in approvals],
    )


async def _serialize_public_posting(
    repository: JobRequisitionRepository,
    posting: JobPosting,
) -> PublicJobPostingListItemRead:
    organization_name = posting.organization.name if posting.organization is not None else ""
    organization_slug = posting.organization.slug if posting.organization is not None else ""
    requisition = await repository.get_matching_requisition_for_posting(
        posting.organizationId,
        posting.title,
    )
    return PublicJobPostingListItemRead(
        id=posting.id,
        organizationId=posting.organizationId,
        organizationName=organization_name,
        organizationSlug=organization_slug,
        title=posting.title,
        description=posting.description,
        requirements=posting.requirements,
        location=requisition.location if requisition is not None else None,
        employmentType=requisition.employmentType.value if requisition is not None else None,
        openings=requisition.openings if requisition is not None else None,
        salaryMin=requisition.salaryMin if requisition is not None else None,
        salaryMax=requisition.salaryMax if requisition is not None else None,
        currency=requisition.currency if requisition is not None else None,
        isRemote=requisition.isRemote if requisition is not None else False,
        targetDate=_to_utc_datetime(requisition.targetDate) if requisition is not None else None,
        skills=list(requisition.skills or []) if requisition is not None else [],
        publishedAt=_to_utc_datetime(posting.publishedAt),
        createdAt=posting.createdAt,
        updatedAt=posting.updatedAt,
    )


async def _create_job_posting_for_requisition(
    repository: JobRequisitionRepository,
    requisition: JobRequisition,
) -> JobPosting:
    now = datetime.now(timezone.utc)
    posting = JobPosting(
        organizationId=requisition.organizationId,
        title=requisition.title,
        slug=await _generate_job_slug(repository, requisition.organizationId, requisition.title),
        description=(requisition.description or "").strip() or requisition.title.strip(),
        requirements=requisition.requirements,
        status=JobPostingStatus.PUBLISHED,
        publishedAt=now,
    )
    posting = await repository.add_job_posting(posting)

    used_stage_slugs: set[str] = set()
    stages = [
        PipelineStage(
            organizationId=requisition.organizationId,
            jobPostingId=posting.id,
            name=stage["name"],
            slug=_generate_stage_slug(str(stage["name"]), used_stage_slugs),
            order=stage["order"],
            color=stage["color"],
            isDefault=stage["isDefault"],
            isFinal=stage["isFinal"],
            stageType=stage["stageType"],
            meetingEnabled=bool(stage["stageType"] == StageType.INTERVIEW),
            offerLetterEnabled=bool(stage["stageType"] == StageType.OFFER),
        )
        for stage in DEFAULT_PIPELINE_STAGES
    ]
    await repository.add_pipeline_stages(stages)
    return posting


async def list_requisitions(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    view_scope: str,
) -> list[JobRequisitionListItemRead]:
    repository = JobRequisitionRepository(db)
    if view_scope == "organization":
        raised_by_id = None
    elif view_scope == "self":
        raised_by_id = actor_member_id
    else:
        raise HTTPException(status_code=403, detail="you dont have permission")
    requisitions = await repository.list_requisitions(organization_id, raised_by_id=raised_by_id)
    return [_serialize_requisition(requisition, actor_member_id) for requisition in requisitions]


async def get_requisition(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    view_scope: str,
    requisition_id: str,
) -> JobRequisitionDetailRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    if view_scope == "self" and requisition.raisedById != actor_member_id:
        raise HTTPException(status_code=403, detail="you dont have permission")
    if view_scope != "self" and view_scope != "organization":
        raise HTTPException(status_code=403, detail="you dont have permission")
    return JobRequisitionDetailRead(**_serialize_requisition(requisition, actor_member_id).model_dump())


async def create_requisition(
    db: AsyncSession,
    organization_id: str,
    raised_by_id: str,
    body: JobRequisitionCreateRequest,
) -> JobRequisitionDetailRead:
    repository = JobRequisitionRepository(db)
    if body.departmentId is not None:
        department = await repository.get_department(organization_id, body.departmentId)
        if department is None:
            raise HTTPException(status_code=404, detail="Department not found")

    requisition = JobRequisition(
        organizationId=organization_id,
        title=body.title.strip(),
        departmentId=body.departmentId,
        employmentType=EmploymentType(body.employmentType),
        openings=body.openings,
        salaryMin=body.salaryMin,
        salaryMax=body.salaryMax,
        currency=body.currency.strip(),
        description=body.description,
        requirements=body.requirements,
        skills=body.skills,
        location=body.location,
        isRemote=body.isRemote,
        raisedById=raised_by_id,
        targetDate=(
            datetime.combine(body.targetDate, datetime.min.time(), tzinfo=timezone.utc)
            if body.targetDate is not None
            else None
        ),
        status=JobRequisitionStatus.DRAFT,
        closedAt=None,
    )
    requisition = await repository.create_requisition(requisition)
    requisition = await repository.get_requisition(organization_id, requisition.id) or requisition
    return JobRequisitionDetailRead(**_serialize_requisition(requisition, raised_by_id).model_dump())


async def submit_requisition(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    requisition_id: str,
) -> JobRequisitionDetailRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    if requisition.raisedById != actor_member_id:
        raise HTTPException(status_code=403, detail="you dont have permission")
    if requisition.status != JobRequisitionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft requisitions can be submitted")

    approvers = await repository.list_org_approvers(organization_id)
    if not approvers:
        raise HTTPException(status_code=400, detail="No job approvers are configured for this organization")

    requisition.status = JobRequisitionStatus.PENDING
    requisition.closedAt = None
    approvals = [
        RequisitionApproval(
            organizationId=organization_id,
            requisitionId=requisition.id,
            approverId=approver.id,
            decision=RequisitionApprovalDecision.PENDING,
            comment=None,
            decidedAt=None,
        )
        for approver in approvers
    ]
    db.add(requisition)
    db.add_all(approvals)
    await db.commit()

    refreshed = await repository.get_requisition(organization_id, requisition_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    return JobRequisitionDetailRead(**_serialize_requisition(refreshed, actor_member_id).model_dump())


async def list_public_postings(
    db: AsyncSession,
) -> list[PublicJobPostingListItemRead]:
    repository = JobRequisitionRepository(db)
    postings = await repository.list_public_postings()
    return [await _serialize_public_posting(repository, posting) for posting in postings]


async def get_public_posting(
    db: AsyncSession,
    posting_id: str,
) -> PublicJobPostingDetailRead:
    repository = JobRequisitionRepository(db)
    posting = await repository.get_public_posting(posting_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return PublicJobPostingDetailRead(**(await _serialize_public_posting(repository, posting)).model_dump())


async def apply_to_public_posting(
    db: AsyncSession,
    posting_id: str,
    body: PublicJobApplicationRequest,
) -> PublicJobApplicationRead:
    repository = JobRequisitionRepository(db)
    posting = await repository.get_public_posting(posting_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    default_stage = await repository.get_default_pipeline_stage(posting.organizationId, posting.id)
    if default_stage is None:
        raise HTTPException(status_code=400, detail="No pipeline stage is configured for this job posting")

    candidate = await repository.get_candidate_by_email(posting.organizationId, body.email)
    if candidate is not None:
        existing_application = await repository.get_candidate_application(
            posting.organizationId,
            candidate.id,
            posting.id,
        )
        if existing_application is not None:
            raise HTTPException(status_code=409, detail="You have already applied to this job")

    if candidate is None:
        candidate = Candidate(
            organizationId=posting.organizationId,
            userId=None,
            firstName=body.firstName,
            lastName=body.lastName,
            email=body.email,
            phone=body.phone,
            linkedinUrl=body.linkedinUrl,
            resumeUrl=body.resumeUrl,
        )
        await repository.add_candidate(candidate)
    else:
        candidate.firstName = body.firstName
        candidate.lastName = body.lastName
        candidate.phone = body.phone
        candidate.linkedinUrl = body.linkedinUrl
        candidate.resumeUrl = body.resumeUrl
        await repository.add_candidate(candidate)

    application = CandidateApplication(
        organizationId=posting.organizationId,
        candidateId=candidate.id,
        jobPostingId=posting.id,
        pipelineStageId=default_stage.id,
        source=ApplicationSource.COMPANY_WEBSITE,
        score=None,
        notes=body.coverLetter,
    )
    await repository.add_application(application)

    history = ApplicationStageHistory(
        organizationId=posting.organizationId,
        applicationId=application.id,
        fromStageId=None,
        toStageId=default_stage.id,
        movedByMemberId=None,
        note="Applied via public careers portal",
    )
    await repository.add_stage_history(history)
    await db.commit()

    return PublicJobApplicationRead(
        applicationId=application.id,
        candidateId=candidate.id,
        jobPostingId=posting.id,
        organizationId=posting.organizationId,
        pipelineStageId=default_stage.id,
    )


async def decide_requisition(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    requisition_id: str,
    decision: RequisitionApprovalDecision,
    body: JobRequisitionDecisionRequest,
) -> JobRequisitionDetailRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    if requisition.status != JobRequisitionStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending requisitions can be reviewed")

    approval = next(
        (item for item in requisition.approvals if item.approverId == actor_member_id),
        None,
    )
    if approval is None:
        raise HTTPException(status_code=403, detail="you dont have permission")
    if approval.decision != RequisitionApprovalDecision.PENDING:
        raise HTTPException(status_code=400, detail="You have already reviewed this requisition")

    approval.decision = decision
    approval.comment = body.comment
    approval.decidedAt = datetime.now(timezone.utc)

    if any(item.decision == RequisitionApprovalDecision.REJECTED for item in requisition.approvals):
        requisition.status = JobRequisitionStatus.REJECTED
    elif all(item.decision == RequisitionApprovalDecision.APPROVED for item in requisition.approvals):
        requisition.status = JobRequisitionStatus.APPROVED
        await _create_job_posting_for_requisition(repository, requisition)
    else:
        requisition.status = JobRequisitionStatus.PENDING

    db.add(approval)
    db.add(requisition)
    await db.commit()

    refreshed = await repository.get_requisition(organization_id, requisition_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    return JobRequisitionDetailRead(**_serialize_requisition(refreshed, actor_member_id).model_dump())


async def close_requisition(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    delete_scope: str,
    requisition_id: str,
) -> JobRequisitionDetailRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    if delete_scope == "self" and requisition.raisedById != actor_member_id:
        raise HTTPException(status_code=403, detail="you dont have permission")
    if delete_scope != "self" and delete_scope != "organization":
        raise HTTPException(status_code=403, detail="you dont have permission")

    requisition.status = JobRequisitionStatus.CLOSED
    requisition.closedAt = datetime.now(timezone.utc)
    db.add(requisition)
    await db.commit()

    refreshed = await repository.get_requisition(organization_id, requisition_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    return JobRequisitionDetailRead(**_serialize_requisition(refreshed, actor_member_id).model_dump())
