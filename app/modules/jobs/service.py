from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department_member import DepartmentMember
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
    StageEvaluationCategory,
    StageType,
)
from app.models.team_member import TeamMember
from app.modules.jobs.repository import JobRequisitionRepository
from app.modules.jobs.schema import (
    CreatePipelineStageRequest,
    ImportableJobPostingRead,
    ImportPipelineRequest,
    JobRequisitionApprovalRead,
    JobRequisitionApprovalSummaryRead,
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
from app.shared.notifications.email import (
    send_requisition_decided,
    send_requisition_submitted,
)
from app.shared.utils.slugs import generate_unique_slug, slugify

_SCOPE_RANK = {"none": 0, "self": 1, "team": 2, "department": 3, "organization": 4}


async def _get_member_department_ids(db: AsyncSession, member_id: str) -> list[str]:
    result = await db.execute(
        select(DepartmentMember.departmentId).where(DepartmentMember.memberId == member_id)
    )
    return [row[0] for row in result.all()]


async def _get_team_member_ids(db: AsyncSession, member_id: str) -> list[str]:
    """Get all member IDs in the same teams as the given member."""
    result = await db.execute(
        select(TeamMember.teamId).where(TeamMember.memberId == member_id)
    )
    team_ids = [row[0] for row in result.all()]
    if not team_ids:
        return []

    result = await db.execute(
        select(TeamMember.memberId).where(TeamMember.teamId.in_(team_ids))
    )
    return list({row[0] for row in result.all()})


async def _check_single_requisition_access(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    scope: str,
    requisition: JobRequisition,
) -> None:
    """Raise 403 if the actor's scope doesn't grant access to this requisition."""
    if scope == "organization":
        return
    if scope == "department":
        if requisition.departmentId is None:
            raise HTTPException(status_code=403, detail="you dont have permission")
        dept_ids = await _get_member_department_ids(db, actor_member_id)
        if requisition.departmentId not in dept_ids:
            raise HTTPException(status_code=403, detail="you dont have permission")
        return
    if scope == "team":
        team_member_ids = await _get_team_member_ids(db, actor_member_id)
        if requisition.raisedById not in team_member_ids:
            raise HTTPException(status_code=403, detail="you dont have permission")
        return
    if scope == "self":
        if requisition.raisedById != actor_member_id:
            raise HTTPException(status_code=403, detail="you dont have permission")
        return
    raise HTTPException(status_code=403, detail="you dont have permission")

SETUP_DEFAULT_PIPELINE_STAGES: list[dict[str, object]] = [
    {"name": "Screening", "stageType": StageType.DEFAULT, "isFinal": False},
    {"name": "Interview", "stageType": StageType.INTERVIEW, "isFinal": False},
    {"name": "Offer", "stageType": StageType.OFFER, "isFinal": False},
    {"name": "Hired", "stageType": StageType.HIRED, "isFinal": True},
    {"name": "Rejected", "stageType": StageType.REJECTED, "isFinal": True},
]


def _slugify(value: str) -> str:
    return slugify(value, fallback="item")


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
    return generate_unique_slug(name, used, fallback="stage")


def _to_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_target_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc_datetime(value)
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)


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


def _is_applied_stage(stage: PipelineStage) -> bool:
    return stage.name.strip().lower() == "applied" and stage.order == 1


def _serialize_pipeline_stage(stage: PipelineStage) -> PipelineStageRead:
    return PipelineStageRead(
        id=stage.id,
        jobPostingId=stage.jobPostingId,
        name=stage.name,
        slug=stage.slug,
        order=stage.order,
        color=stage.color,
        isDefault=stage.isDefault,
        isFinal=stage.isFinal,
        stageType=stage.stageType.value,
        meetingEnabled=stage.meetingEnabled,
        offerLetterEnabled=stage.offerLetterEnabled,
        evaluationEnabled=stage.evaluationEnabled,
        sheetEnabled=stage.sheetEnabled,
        evaluationType=stage.evaluationType,
        evaluationIncludeTotal=stage.evaluationIncludeTotal,
        evaluationIncludeAnalysis=stage.evaluationIncludeAnalysis,
        dueDate=_to_utc_datetime(stage.dueDate),
        extendToNextWorkingDay=stage.extendToNextWorkingDay,
        evaluationCategories=[
            {
                "id": category.id,
                "stageId": category.stageId,
                "name": category.name,
                "type": category.valueType,
                "maxScore": category.maxScore,
                "order": category.order,
            }
            for category in sorted(stage.evaluationCategories or [], key=lambda item: item.order)
        ],
    )


def _serialize_pipeline_board(job_posting_id: str, stages: list[PipelineStage]) -> PipelineBoardRead:
    ordered_stages = sorted(stages, key=lambda stage: stage.order)
    return PipelineBoardRead(
        jobPostingId=job_posting_id,
        stages=[_serialize_pipeline_stage(stage) for stage in ordered_stages],
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
    replacement_for_name = None
    if requisition.replacementFor is not None and requisition.replacementFor.user is not None:
        replacement_for_name = (
            requisition.replacementFor.user.name or requisition.replacementFor.user.email
        )
    year = str(requisition.createdAt.year) if requisition.createdAt else str(datetime.now().year)
    req_num = requisition.requisitionNumber
    requisition_label = f"REQ-{year}-{req_num:04d}" if req_num is not None else None
    review_statuses = {
        JobRequisitionStatus.PENDING,
        JobRequisitionStatus.PENDING_APPROVAL,
        JobRequisitionStatus.PARTIALLY_APPROVED,
    }
    response_status = (
        JobRequisitionStatus.PENDING_APPROVAL
        if requisition.status == JobRequisitionStatus.PENDING
        else requisition.status
    )

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
        status=response_status,
        createdAt=requisition.createdAt,
        updatedAt=requisition.updatedAt,
        closedAt=_to_utc_datetime(requisition.closedAt),
        hiringReason=requisition.hiringReason,
        priority=requisition.priority or "MEDIUM",
        replacementForId=requisition.replacementForId,
        replacementForName=replacement_for_name,
        businessJustification=requisition.businessJustification,
        salaryVisibility=requisition.salaryVisibility or "INTERNAL_ONLY",
        experienceLevel=requisition.experienceLevel,
        minExperience=requisition.minExperience,
        education=requisition.education,
        certifications=list(requisition.certifications or []),
        roleSummary=requisition.roleSummary,
        responsibilities=requisition.responsibilities,
        requirementsRich=requisition.requirementsRich,
        benefits=requisition.benefits,
        aboutTeam=requisition.aboutTeam,
        requisitionNumber=requisition.requisitionNumber,
        requisitionLabel=requisition_label,
        canEdit=(
            requisition.raisedById == actor_member_id
            and requisition.status == JobRequisitionStatus.DRAFT
        ),
        approvalSummary=_build_approval_summary(approvals),
        currentUserApprovalDecision=current_approval.decision if current_approval is not None else None,
        currentUserCanApprove=(
            requisition.status in review_statuses
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
    requisition = posting.requisition
    if requisition is None:
        requisition = await repository.get_matching_requisition_for_posting(
            posting.organizationId,
            posting.title,
        )
    department_name = requisition.department.name if requisition is not None and requisition.department is not None else None

    return PublicJobPostingListItemRead(
        id=posting.id,
        organizationId=posting.organizationId,
        organizationName=organization_name,
        organizationSlug=organization_slug,
        title=posting.title,
        description=posting.description,
        requirements=posting.requirements,
        roleSummary=requisition.roleSummary if requisition is not None else None,
        responsibilities=requisition.responsibilities if requisition is not None else None,
        requirementsRich=requisition.requirementsRich if requisition is not None else None,
        benefits=requisition.benefits if requisition is not None else None,
        aboutTeam=requisition.aboutTeam if requisition is not None else None,
        requisitionId=posting.requisitionId,
        location=requisition.location if requisition is not None else None,
        employmentType=requisition.employmentType.value if requisition is not None else None,
        openings=requisition.openings if requisition is not None else None,
        salaryMin=requisition.salaryMin if requisition is not None else None,
        salaryMax=requisition.salaryMax if requisition is not None else None,
        currency=requisition.currency if requisition is not None else None,
        isRemote=requisition.isRemote if requisition is not None else False,
        targetDate=_to_utc_datetime(requisition.targetDate) if requisition is not None else None,
        skills=list(requisition.skills or []) if requisition is not None else [],
        experienceLevel=requisition.experienceLevel if requisition is not None else None,
        minExperience=requisition.minExperience if requisition is not None else None,
        education=requisition.education if requisition is not None else None,
        certifications=list(requisition.certifications or []) if requisition is not None else [],
        departmentName=department_name,
        hiringReason=requisition.hiringReason if requisition is not None else None,
        publishedAt=_to_utc_datetime(posting.publishedAt),
        createdAt=posting.createdAt,
        updatedAt=posting.updatedAt,
    )


async def _create_job_posting_for_requisition(
    repository: JobRequisitionRepository,
    requisition: JobRequisition,
) -> JobPosting:
    now = datetime.now(timezone.utc)
    rich_sections = [
        requisition.roleSummary,
        requisition.responsibilities,
        requisition.requirementsRich,
        requisition.benefits,
        requisition.aboutTeam,
    ]
    description = "\n\n".join(section.strip() for section in rich_sections if section and section.strip())
    posting = JobPosting(
        organizationId=requisition.organizationId,
        requisitionId=requisition.id,
        title=requisition.title,
        slug=await _generate_job_slug(repository, requisition.organizationId, requisition.title),
        description=(description or requisition.description or requisition.title).strip(),
        requirements=requisition.requirementsRich or requisition.requirements,
        status=JobPostingStatus.PUBLISHED,
        publishedAt=now,
    )
    posting = await repository.add_job_posting(posting)

    applied_stage = PipelineStage(
        organizationId=requisition.organizationId,
        jobPostingId=posting.id,
        name="Applied",
        slug="applied",
        order=1.0,
        color=None,
        isDefault=True,
        isFinal=False,
        stageType=StageType.DEFAULT,
        meetingEnabled=False,
        offerLetterEnabled=False,
    )
    await repository.add_pipeline_stages([applied_stage])
    return posting


async def _generate_requisition_number(
    repository: JobRequisitionRepository,
    organization_id: str,
) -> int:
    max_num = await repository.get_max_requisition_number(organization_id)
    return (max_num or 0) + 1


async def _log_activity(
    repository: JobRequisitionRepository,
    organization_id: str,
    requisition_id: str,
    actor_id: str,
    action: str,
    field_changes: dict | None = None,
    comment: str | None = None,
) -> None:
    from app.models.recruitment import RequisitionActivityLog

    log = RequisitionActivityLog(
        organizationId=organization_id,
        requisitionId=requisition_id,
        actorId=actor_id,
        action=action,
        fieldChanges=field_changes,
        comment=comment,
    )
    await repository.add_activity_log(log)
    await repository.db.commit()


def _missing_submission_fields(requisition: JobRequisition) -> list[str]:
    missing = []
    if not requisition.title:
        missing.append("title")
    if not requisition.departmentId:
        missing.append("department")
    if not requisition.employmentType:
        missing.append("employment type")
    if not requisition.openings or requisition.openings < 1:
        missing.append("openings")
    if not requisition.hiringReason:
        missing.append("hiring reason")
    if not (
        requisition.roleSummary
        or requisition.responsibilities
        or requisition.requirementsRich
        or requisition.description
        or requisition.requirements
    ):
        missing.append("at least one content section")
    return missing


def _validate_submission_ready(requisition: JobRequisition) -> None:
    missing = _missing_submission_fields(requisition)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot submit: missing required fields: {', '.join(missing)}",
        )


def _validate_approval_ready(requisition: JobRequisition) -> None:
    missing = _missing_submission_fields(requisition)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve: missing required fields: {', '.join(missing)}",
        )
    if requisition.salaryMax is not None and requisition.salaryMin is not None:
        if requisition.salaryMax < requisition.salaryMin:
            raise HTTPException(
                status_code=400,
                detail="salaryMax must be greater than or equal to salaryMin",
            )


def _validate_requisition_salary_range(requisition: JobRequisition) -> None:
    if requisition.salaryMax is None or requisition.salaryMin is None:
        return
    if requisition.salaryMax < requisition.salaryMin:
        raise HTTPException(
            status_code=400,
            detail="salaryMax must be greater than or equal to salaryMin",
        )


async def _validate_department_if_present(
    repository: JobRequisitionRepository,
    organization_id: str,
    department_id: str | None,
) -> None:
    if department_id is None:
        return
    department = await repository.get_department(organization_id, department_id)
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")


async def _validate_replacement_if_present(
    repository: JobRequisitionRepository,
    organization_id: str,
    replacement_for_id: str | None,
) -> None:
    if replacement_for_id is None:
        return
    member = await repository.get_member(organization_id, replacement_for_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Replacement member not found")


def _apply_requisition_updates(
    requisition: JobRequisition,
    body: JobRequisitionUpdateRequest | JobRequisitionDecisionRequest,
) -> list[str]:
    changed_fields: list[str] = []
    update_fields = {
        "title",
        "departmentId",
        "employmentType",
        "openings",
        "hiringReason",
        "priority",
        "replacementForId",
        "businessJustification",
        "salaryMin",
        "salaryMax",
        "currency",
        "salaryVisibility",
        "skills",
        "experienceLevel",
        "minExperience",
        "education",
        "certifications",
        "roleSummary",
        "responsibilities",
        "requirementsRich",
        "benefits",
        "aboutTeam",
        "description",
        "requirements",
        "location",
        "isRemote",
        "targetDate",
    }
    for field_name in body.model_fields_set:
        if field_name not in update_fields:
            continue
        value = getattr(body, field_name)
        if value is None:
            continue
        if field_name == "title":
            value = value.strip()
        elif field_name == "currency":
            value = value.strip()
        elif field_name == "employmentType":
            value = EmploymentType(value)
        elif field_name == "targetDate":
            value = _to_target_datetime(value)
        setattr(requisition, field_name, value)
        changed_fields.append(field_name)
    return changed_fields


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
    elif view_scope == "department":
        department_ids = await _get_member_department_ids(db, actor_member_id)
        requisitions = await repository.list_requisitions(
            organization_id, department_ids=department_ids
        )
        return [_serialize_requisition(requisition, actor_member_id) for requisition in requisitions]
    elif view_scope == "team":
        team_member_ids = await _get_team_member_ids(db, actor_member_id)
        requisitions = await repository.list_requisitions(
            organization_id, team_member_ids=team_member_ids
        )
        return [_serialize_requisition(requisition, actor_member_id) for requisition in requisitions]
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
    await _check_single_requisition_access(db, organization_id, actor_member_id, view_scope, requisition)
    return JobRequisitionDetailRead(**_serialize_requisition(requisition, actor_member_id).model_dump())


async def _get_pipeline_posting(
    db: AsyncSession,
    repository: JobRequisitionRepository,
    organization_id: str,
    actor_member_id: str,
    scope: str,
    requisition_id: str,
) -> JobPosting:
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    await _check_single_requisition_access(db, organization_id, actor_member_id, scope, requisition)

    posting = await repository.get_job_posting_by_requisition(organization_id, requisition_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found for this requisition")
    return posting


async def _generate_pipeline_stage_slug(
    repository: JobRequisitionRepository,
    organization_id: str,
    job_posting_id: str,
    name: str,
) -> str:
    used_slugs = set(await repository.list_stage_slugs(organization_id, job_posting_id))
    return _generate_stage_slug(name, used_slugs)


async def _replace_setup_stages(
    repository: JobRequisitionRepository,
    organization_id: str,
    job_posting_id: str,
) -> tuple[PipelineStage | None, set[str]]:
    stages = await repository.list_pipeline_stages(organization_id, job_posting_id)
    applied = next((stage for stage in stages if _is_applied_stage(stage)), None)
    removable_stages = [stage for stage in stages if stage.id != applied.id] if applied else stages
    if removable_stages:
        await repository.delete_pipeline_stages(removable_stages)
    if applied is None:
        applied = PipelineStage(
            organizationId=organization_id,
            jobPostingId=job_posting_id,
            name="Applied",
            slug="applied",
            order=1.0,
            color=None,
            isDefault=True,
            isFinal=False,
            stageType=StageType.DEFAULT,
            meetingEnabled=False,
            offerLetterEnabled=False,
        )
        await repository.create_pipeline_stage(applied)
    used_slugs = {applied.slug} if applied is not None else set()
    return applied, used_slugs


async def get_requisition_pipeline(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    view_scope: str,
    requisition_id: str,
) -> PipelineBoardRead:
    repository = JobRequisitionRepository(db)
    posting = await _get_pipeline_posting(
        db,
        repository,
        organization_id,
        actor_member_id,
        view_scope,
        requisition_id,
    )
    stages = await repository.list_pipeline_stages(organization_id, posting.id)
    return _serialize_pipeline_board(posting.id, stages)


async def create_pipeline_stage(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    edit_scope: str,
    requisition_id: str,
    body: CreatePipelineStageRequest,
) -> PipelineStageRead:
    repository = JobRequisitionRepository(db)
    posting = await _get_pipeline_posting(
        db,
        repository,
        organization_id,
        actor_member_id,
        edit_scope,
        requisition_id,
    )
    stages = await repository.list_pipeline_stages(organization_id, posting.id)
    next_order = max((stage.order for stage in stages), default=0.0) + 1.0
    stage_type = StageType(body.stageType)
    stage = PipelineStage(
        organizationId=organization_id,
        jobPostingId=posting.id,
        name=body.name,
        slug=await _generate_pipeline_stage_slug(repository, organization_id, posting.id, body.name),
        order=next_order,
        color=None,
        isDefault=not stages and body.name.strip().lower() == "applied",
        isFinal=stage_type in {StageType.HIRED, StageType.REJECTED},
        stageType=stage_type,
        meetingEnabled=stage_type == StageType.INTERVIEW,
        offerLetterEnabled=stage_type == StageType.OFFER,
        evaluationEnabled=body.evaluationEnabled,
        sheetEnabled=body.sheetEnabled if body.evaluationEnabled else False,
        evaluationType=body.evaluationType if body.evaluationEnabled else None,
        evaluationIncludeTotal=body.evaluationIncludeTotal if body.evaluationEnabled else False,
        evaluationIncludeAnalysis=body.evaluationIncludeAnalysis if body.evaluationEnabled else False,
        dueDate=body.dueDate,
        extendToNextWorkingDay=body.extendToNextWorkingDay,
    )
    await repository.create_pipeline_stage(stage)
    if body.evaluationEnabled and body.evaluationCategories:
        await repository.create_stage_evaluation_categories(
            [
                StageEvaluationCategory(
                    organizationId=organization_id,
                    stageId=stage.id,
                    name=category.name,
                    valueType=category.type,
                    maxScore=category.maxScore,
                    order=category.order or index,
                )
                for index, category in enumerate(body.evaluationCategories, start=1)
            ]
        )
    await db.commit()

    refreshed = await repository.list_pipeline_stages(organization_id, posting.id)
    created = next((item for item in refreshed if item.id == stage.id), stage)
    return _serialize_pipeline_stage(created)


async def create_default_pipeline(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    edit_scope: str,
    requisition_id: str,
) -> PipelineBoardRead:
    repository = JobRequisitionRepository(db)
    posting = await _get_pipeline_posting(
        db,
        repository,
        organization_id,
        actor_member_id,
        edit_scope,
        requisition_id,
    )
    applied_stage, used_slugs = await _replace_setup_stages(repository, organization_id, posting.id)
    stages: list[PipelineStage] = []
    start_order = applied_stage.order if applied_stage is not None else 0.0
    for index, stage_data in enumerate(SETUP_DEFAULT_PIPELINE_STAGES, start=1):
        stage_type = stage_data["stageType"]
        stage_name = str(stage_data["name"])
        stages.append(
            PipelineStage(
                organizationId=organization_id,
                jobPostingId=posting.id,
                name=stage_name,
                slug=_generate_stage_slug(stage_name, used_slugs),
                order=start_order + float(index),
                color=None,
                isDefault=True,
                isFinal=bool(stage_data["isFinal"]),
                stageType=stage_type,
                meetingEnabled=stage_type == StageType.INTERVIEW,
                offerLetterEnabled=stage_type == StageType.OFFER,
            )
        )
    await repository.add_pipeline_stages(stages)
    await db.commit()

    refreshed = await repository.list_pipeline_stages(organization_id, posting.id)
    return _serialize_pipeline_board(posting.id, refreshed)


async def import_pipeline(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    edit_scope: str,
    requisition_id: str,
    body: ImportPipelineRequest,
) -> PipelineBoardRead:
    repository = JobRequisitionRepository(db)
    target_posting = await _get_pipeline_posting(
        db,
        repository,
        organization_id,
        actor_member_id,
        edit_scope,
        requisition_id,
    )
    if body.sourceJobPostingId == target_posting.id:
        raise HTTPException(status_code=400, detail="Choose a different job to import from")
    source_stages = await repository.get_pipeline_stages_for_import(
        organization_id,
        body.sourceJobPostingId,
    )
    if not source_stages:
        raise HTTPException(status_code=404, detail="Source job posting not found")

    importable_stages = [stage for stage in source_stages if not _is_applied_stage(stage)]
    if not importable_stages:
        raise HTTPException(status_code=400, detail="The selected job has no stages to import")

    applied_stage, used_slugs = await _replace_setup_stages(repository, organization_id, target_posting.id)
    start_order = applied_stage.order if applied_stage is not None else 0.0
    created_stages: list[tuple[PipelineStage, PipelineStage]] = []
    for index, source_stage in enumerate(importable_stages, start=1):
        copied_stage = PipelineStage(
            organizationId=organization_id,
            jobPostingId=target_posting.id,
            name=source_stage.name,
            slug=_generate_stage_slug(source_stage.name, used_slugs),
            order=start_order + float(index),
            color=source_stage.color,
            isDefault=source_stage.isDefault,
            isFinal=source_stage.isFinal,
            stageType=source_stage.stageType,
            meetingEnabled=source_stage.meetingEnabled,
            offerLetterEnabled=source_stage.offerLetterEnabled,
            evaluationEnabled=source_stage.evaluationEnabled,
            sheetEnabled=source_stage.sheetEnabled,
            evaluationType=source_stage.evaluationType,
            evaluationIncludeTotal=source_stage.evaluationIncludeTotal,
            evaluationIncludeAnalysis=source_stage.evaluationIncludeAnalysis,
            dueDate=source_stage.dueDate,
            extendToNextWorkingDay=source_stage.extendToNextWorkingDay,
        )
        await repository.create_pipeline_stage(copied_stage)
        created_stages.append((source_stage, copied_stage))

    categories: list[StageEvaluationCategory] = []
    for source_stage, copied_stage in created_stages:
        for category in sorted(source_stage.evaluationCategories or [], key=lambda item: item.order):
            categories.append(
                StageEvaluationCategory(
                    organizationId=organization_id,
                    stageId=copied_stage.id,
                    name=category.name,
                    valueType=category.valueType,
                    maxScore=category.maxScore,
                    order=category.order,
                )
            )
    if categories:
        await repository.create_stage_evaluation_categories(categories)
    await db.commit()

    refreshed = await repository.list_pipeline_stages(organization_id, target_posting.id)
    return _serialize_pipeline_board(target_posting.id, refreshed)


async def get_import_options(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    view_scope: str,
    requisition_id: str,
) -> list[ImportableJobPostingRead]:
    repository = JobRequisitionRepository(db)
    posting = await _get_pipeline_posting(
        db,
        repository,
        organization_id,
        actor_member_id,
        view_scope,
        requisition_id,
    )
    postings = await repository.list_job_postings_for_import(organization_id, posting.id)
    return [
        ImportableJobPostingRead(
            id=posting.id,
            title=posting.title,
            departmentName=(
                posting.requisition.department.name
                if posting.requisition is not None and posting.requisition.department is not None
                else None
            ),
            stageCount=len([stage for stage in posting.pipelineStages if not _is_applied_stage(stage)]),
            stages=[
                _serialize_pipeline_stage(stage)
                for stage in sorted(posting.pipelineStages or [], key=lambda item: item.order)
                if not _is_applied_stage(stage)
            ],
        )
        for posting in postings
    ]


async def create_requisition(
    db: AsyncSession,
    organization_id: str,
    raised_by_id: str,
    body: JobRequisitionCreateRequest,
) -> JobRequisitionDetailRead:
    repository = JobRequisitionRepository(db)
    await _validate_department_if_present(repository, organization_id, body.departmentId)
    await _validate_replacement_if_present(repository, organization_id, body.replacementForId)

    requisition = JobRequisition(
        organizationId=organization_id,
        title=body.title.strip(),
        departmentId=body.departmentId,
        employmentType=EmploymentType(body.employmentType),
        openings=body.openings,
        salaryMin=body.salaryMin,
        salaryMax=body.salaryMax,
        currency=body.currency.strip(),
        description=body.description or body.roleSummary,
        requirements=body.requirements or body.requirementsRich,
        skills=body.skills,
        location=body.location,
        isRemote=body.isRemote,
        raisedById=raised_by_id,
        targetDate=_to_target_datetime(body.targetDate),
        status=JobRequisitionStatus.DRAFT,
        closedAt=None,
        hiringReason=body.hiringReason,
        priority=body.priority or "MEDIUM",
        replacementForId=body.replacementForId,
        businessJustification=body.businessJustification,
        salaryVisibility=body.salaryVisibility or "INTERNAL_ONLY",
        experienceLevel=body.experienceLevel,
        minExperience=body.minExperience,
        education=body.education,
        certifications=body.certifications,
        roleSummary=body.roleSummary,
        responsibilities=body.responsibilities,
        requirementsRich=body.requirementsRich,
        benefits=body.benefits,
        aboutTeam=body.aboutTeam,
        requisitionNumber=await _generate_requisition_number(repository, organization_id),
    )
    requisition = await repository.create_requisition(requisition)
    await _log_activity(repository, organization_id, requisition.id, raised_by_id, "CREATED")
    requisition = await repository.get_requisition(organization_id, requisition.id) or requisition
    return JobRequisitionDetailRead(**_serialize_requisition(requisition, raised_by_id).model_dump())


async def update_requisition(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    requisition_id: str,
    body: JobRequisitionUpdateRequest,
) -> JobRequisitionDetailRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    if requisition.raisedById != actor_member_id:
        raise HTTPException(status_code=403, detail="you dont have permission")
    if requisition.status != JobRequisitionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft requisitions can be edited")

    if "departmentId" in body.model_fields_set:
        await _validate_department_if_present(repository, organization_id, body.departmentId)
    if "replacementForId" in body.model_fields_set:
        await _validate_replacement_if_present(repository, organization_id, body.replacementForId)

    changed_fields = _apply_requisition_updates(requisition, body)
    if changed_fields:
        _validate_requisition_salary_range(requisition)
        await repository.save(requisition)
        await _log_activity(
            repository,
            organization_id,
            requisition.id,
            actor_member_id,
            "EDITED",
            field_changes={"fields": changed_fields},
        )

    refreshed = await repository.get_requisition(organization_id, requisition_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    return JobRequisitionDetailRead(**_serialize_requisition(refreshed, actor_member_id).model_dump())


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
    _validate_submission_ready(requisition)

    approvers = await repository.list_org_approvers(organization_id)
    if not approvers:
        raise HTTPException(status_code=400, detail="No job approvers are configured for this organization")

    requisition.status = JobRequisitionStatus.PENDING_APPROVAL
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
    await _log_activity(repository, organization_id, requisition.id, actor_member_id, "SUBMITTED")

    refreshed = await repository.get_requisition(organization_id, requisition_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    if refreshed.organization is not None:
        raiser_name = (
            refreshed.raisedBy.user.name
            if refreshed.raisedBy is not None
            and refreshed.raisedBy.user is not None
            and refreshed.raisedBy.user.name
            else "A team member"
        )
        await send_requisition_submitted(
            refreshed,
            refreshed.organization.slug,
            approvers,
            raiser_name,
        )
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
    valid_statuses = {
        JobRequisitionStatus.PENDING,
        JobRequisitionStatus.PENDING_APPROVAL,
        JobRequisitionStatus.PARTIALLY_APPROVED,
    }
    if requisition.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Only pending requisitions can be reviewed")
    if decision == RequisitionApprovalDecision.REJECTED and not (body.comment or "").strip():
        raise HTTPException(status_code=400, detail="Comment is required to reject a requisition")

    approval = next(
        (item for item in requisition.approvals if item.approverId == actor_member_id),
        None,
    )
    if approval is None:
        raise HTTPException(status_code=403, detail="you dont have permission")
    if approval.decision != RequisitionApprovalDecision.PENDING:
        raise HTTPException(status_code=400, detail="You have already reviewed this requisition")

    if decision == RequisitionApprovalDecision.APPROVED:
        if "departmentId" in body.model_fields_set:
            await _validate_department_if_present(repository, organization_id, body.departmentId)
        if "replacementForId" in body.model_fields_set:
            await _validate_replacement_if_present(repository, organization_id, body.replacementForId)
        _apply_requisition_updates(requisition, body)
        _validate_requisition_salary_range(requisition)
        is_final_approval = not any(
            item.id != approval.id and item.decision == RequisitionApprovalDecision.PENDING
            for item in requisition.approvals
        )
        if is_final_approval:
            _validate_approval_ready(requisition)

    approval.decision = decision
    approval.comment = body.comment
    approval.decidedAt = datetime.now(timezone.utc)

    if any(item.decision == RequisitionApprovalDecision.REJECTED for item in requisition.approvals):
        requisition.status = JobRequisitionStatus.REJECTED
        log_action = "REJECTED"
    elif all(item.decision == RequisitionApprovalDecision.APPROVED for item in requisition.approvals):
        requisition.status = JobRequisitionStatus.APPROVED
        log_action = "APPROVED"
        await _create_job_posting_for_requisition(repository, requisition)
    else:
        requisition.status = JobRequisitionStatus.PARTIALLY_APPROVED
        log_action = "APPROVED"

    db.add(approval)
    db.add(requisition)
    await db.commit()
    await _log_activity(
        repository,
        organization_id,
        requisition.id,
        actor_member_id,
        log_action,
        comment=approval.comment,
    )

    refreshed = await repository.get_requisition(organization_id, requisition_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    if refreshed.organization is not None and refreshed.raisedBy is not None:
        await send_requisition_decided(
            refreshed,
            refreshed.organization.slug,
            refreshed.raisedBy,
            log_action,
            approval.comment,
        )
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
    await _check_single_requisition_access(db, organization_id, actor_member_id, delete_scope, requisition)
    closable_statuses = {
        JobRequisitionStatus.APPROVED,
        JobRequisitionStatus.PUBLISHED,
        JobRequisitionStatus.ACTIVE_HIRING,
        JobRequisitionStatus.FILLED,
        JobRequisitionStatus.REJECTED,
        JobRequisitionStatus.PENDING_APPROVAL,
        JobRequisitionStatus.PARTIALLY_APPROVED,
        JobRequisitionStatus.PENDING,
    }
    if requisition.status not in closable_statuses:
        raise HTTPException(status_code=400, detail="This requisition cannot be closed")

    requisition.status = JobRequisitionStatus.CLOSED
    requisition.closedAt = datetime.now(timezone.utc)
    db.add(requisition)
    await db.commit()
    await _log_activity(repository, organization_id, requisition.id, actor_member_id, "CLOSED")

    refreshed = await repository.get_requisition(organization_id, requisition_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    return JobRequisitionDetailRead(**_serialize_requisition(refreshed, actor_member_id).model_dump())


async def reopen_requisition(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    create_scope: str,
    requisition_id: str,
) -> JobRequisitionDetailRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    await _check_single_requisition_access(db, organization_id, actor_member_id, create_scope, requisition)
    if requisition.status not in (JobRequisitionStatus.CLOSED, JobRequisitionStatus.ARCHIVED):
        raise HTTPException(status_code=400, detail="Only closed/archived requisitions can be reopened")

    requisition.status = JobRequisitionStatus.DRAFT
    requisition.closedAt = None
    db.add(requisition)
    await db.commit()
    await _log_activity(repository, organization_id, requisition.id, actor_member_id, "REOPENED")

    refreshed = await repository.get_requisition(organization_id, requisition_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    return JobRequisitionDetailRead(**_serialize_requisition(refreshed, actor_member_id).model_dump())


async def get_requisition_activity(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    view_scope: str,
    requisition_id: str,
) -> list[dict]:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    await _check_single_requisition_access(db, organization_id, actor_member_id, view_scope, requisition)

    logs = await repository.list_activity_logs(organization_id, requisition_id)
    result = []
    for log in logs:
        actor_name = None
        if log.actor is not None and log.actor.user is not None:
            actor_name = log.actor.user.name or log.actor.user.email
        result.append(
            {
                "id": log.id,
                "actorId": log.actorId,
                "actorName": actor_name,
                "action": log.action,
                "fieldChanges": log.fieldChanges,
                "comment": log.comment,
                "createdAt": log.createdAt.isoformat() if log.createdAt else None,
            }
        )
    return result
