from __future__ import annotations

from datetime import UTC, datetime

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.department_member import DepartmentMember
from app.models.member import Member
from app.models.recruitment import (
    ApplicationSource,
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    EmploymentType,
    JobPosting,
    JobPostingStatus,
    JobRequisition,
    JobRequisitionRules,
    JobRequisitionStatus,
    PipelineStage,
    RequisitionApproval,
    RequisitionApprovalDecision,
    StageType,
)
from app.models.user import User
from app.models.team_member import TeamMember
from app.modules.ai_scoring.service import (
    analyze_resume_for_application_task,
    create_pending_resume_analysis,
)
from app.modules.jobs.repository import JobRequisitionRepository
from app.modules.jobs.schema import (
    CreatePipelineStageRequest,
    ImportableJobPostingRead,
    ImportPipelineRequest,
    JobFormMetaRead,
    JobRequisitionAiAnalysisRead,
    JobRequisitionApprovalRead,
    JobRequisitionApprovalSummaryRead,
    JobRequisitionCreateRequest,
    JobRequisitionDecisionRequest,
    JobRequisitionDetailRead,
    JobRequisitionListItemRead,
    JobRequisitionRulesRead,
    JobRequisitionUpdateRequest,
    JobLookupOptionRead,
    PipelineBoardRead,
    PipelineStageRead,
    PublicJobApplicationRead,
    PublicJobApplicationRequest,
    PublicJobPostingDetailRead,
    PublicJobPostingListItemRead,
    RequisitionAiAnalysisStatsRead,
    RequisitionAiCandidateRead,
)
from app.shared.notifications.email import (
    send_requisition_decided,
    send_requisition_submitted,
)
from app.shared.skill_aliases import (
    SKILL_ALIASES,
    contains_skill_phrase,
    is_generic_skill_anchor,
    normalize_keyword,
    normalize_search_text,
)
from app.shared.utils.slugs import generate_unique_slug, slugify

_SCOPE_RANK = {"none": 0, "self": 1, "team": 2, "department": 3, "organization": 4}
REQUISITION_RULES_VERSION = "1.2"
TOTAL_SCORE_POINTS = 100
MAX_EXPERIENCE_POINTS = 40
MAX_SKILL_POINTS = 60
MAX_EDUCATION_POINTS = 10
MAX_CERTIFICATION_POINTS = 10
MAX_DERIVED_SKILL_ANCHORS = 12
OPEN_REQUISITION_STATUSES = [
    JobRequisitionStatus.APPROVED,
    JobRequisitionStatus.PUBLISHED,
    JobRequisitionStatus.ACTIVE_HIRING,
]

_NO_KNOCKOUT_VALUES = {
    "none",
    "no",
    "n/a",
    "na",
    "nil",
    "not applicable",
    "no knockout",
    "no knockout rule",
}


def _display_member_label(name: str | None, email: str | None, member_id: str) -> str:
    normalized_name = (name or "").strip()
    normalized_email = (email or "").strip()
    if normalized_name and normalized_name != normalized_email:
        return normalized_name
    if normalized_email:
        local_part = (
            normalized_email.split("@", 1)[0]
            .replace(".", " ")
            .replace("_", " ")
            .replace("-", " ")
            .strip()
        )
        if local_part:
            return " ".join(part.capitalize() for part in local_part.split())
        return normalized_email
    return member_id


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


async def get_job_form_meta(
    db: AsyncSession,
    organization_id: str,
) -> JobFormMetaRead:
    members_result = await db.execute(
        select(Member.id, User.name, User.email)
        .join(User, User.id == Member.userId)
        .where(Member.organizationId == organization_id)
        .order_by(User.name.asc().nullslast(), User.email.asc())
    )
    departments_result = await db.execute(
        select(Department.id, Department.name)
        .where(
            Department.organizationId == organization_id,
            Department.status == "ACTIVE",
        )
        .order_by(Department.name.asc())
    )
    return JobFormMetaRead(
        members=[
            JobLookupOptionRead(
                id=member_id,
                label=_display_member_label(name, email, member_id),
                email=email,
            )
            for member_id, name, email in members_result.all()
        ],
        departments=[
            JobLookupOptionRead(id=department_id, label=name)
            for department_id, name in departments_result.all()
        ],
    )


async def _check_single_requisition_access(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    scope: str,
    requisition: JobRequisition,
    *,
    allow_open: bool = False,
) -> None:
    """Raise 403 if the actor's scope doesn't grant access to this requisition."""
    if allow_open and requisition.status in OPEN_REQUISITION_STATUSES:
        return
    if scope == "organization":
        return
    if scope == "public_open":
        if requisition.raisedById == actor_member_id:
            return
        raise HTTPException(status_code=403, detail="you dont have permission")
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
    {"name": "Accepted", "stageType": StageType.HIRED, "isFinal": True},
    {"name": "Rejected", "stageType": StageType.REJECTED, "isFinal": True},
]


def _normalize_rule_keyword(value: str) -> str:
    return normalize_keyword(value)


def _normalize_search_text(value: object) -> str:
    return normalize_search_text(value)


def _contains_skill_phrase(text: str, phrase: str) -> bool:
    return contains_skill_phrase(text, phrase)


def _normalize_optional_knockout_rule(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if normalize_keyword(normalized) in _NO_KNOCKOUT_VALUES:
        return None
    return normalized


def _is_generic_skill_anchor(value: str) -> bool:
    return is_generic_skill_anchor(value)


def _derive_skill_anchors(requisition: JobRequisition) -> list[str]:
    source_text = "\n".join(
        item
        for item in [
            requisition.title,
            requisition.roleSummary,
            requisition.responsibilities,
            requisition.requirementsRich,
            requisition.requirements,
            requisition.description,
        ]
        if item
    )
    normalized_text = _normalize_search_text(source_text)
    if not normalized_text:
        return []

    anchors: list[str] = []
    for anchor, aliases in SKILL_ALIASES.items():
        if any(_contains_skill_phrase(normalized_text, alias) for alias in aliases):
            anchors.append(anchor)
        if len(anchors) >= MAX_DERIVED_SKILL_ANCHORS:
            break
    return anchors


def _education_keywords(value: str | None) -> list[str]:
    normalized = _normalize_search_text(value)
    if not normalized:
        return []
    keywords: list[str] = []
    if "bachelor" in normalized or "bachelors" in normalized:
        keywords.append("bachelor")
    if "master" in normalized or "masters" in normalized:
        keywords.append("master")
    if "computer science" in normalized:
        keywords.append("computer science")
    if "engineering" in normalized:
        keywords.append("engineering")
    return _unique_normalized(keywords or [str(value)])


def _unique_normalized(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        item = _normalize_rule_keyword(value)
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _distribute_points(total_points: int, keys: list[str]) -> dict[str, int]:
    if not keys:
        return {}
    base = total_points // len(keys)
    remainder = total_points % len(keys)
    weights: dict[str, int] = {}
    for index, key in enumerate(keys):
        weights[key] = base + (1 if index < remainder else 0)
    return weights


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


def _assert_single_stage_type(
    stages: list[PipelineStage],
    stage_type: StageType,
    *,
    excluded_stage_id: str | None = None,
) -> None:
    protected_types = {
        StageType.OFFER: "This job already has an offer stage.",
        StageType.HIRED: "This job already has an accepted stage.",
        StageType.REJECTED: "This job already has a rejected stage.",
    }
    message = protected_types.get(stage_type)
    if message is None:
        return
    has_existing = any(
        stage.stageType == stage_type and stage.id != excluded_stage_id
        for stage in stages
    )
    if has_existing:
        raise HTTPException(status_code=409, detail=message)


def _to_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_target_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc_datetime(value)
    return datetime.combine(value, datetime.min.time(), tzinfo=UTC)


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
        dueDate=_to_utc_datetime(stage.dueDate),
        extendToNextWorkingDay=stage.extendToNextWorkingDay,
    )


def _serialize_pipeline_board(job_posting_id: str, stages: list[PipelineStage]) -> PipelineBoardRead:
    ordered_stages = sorted(stages, key=lambda stage: stage.order)
    return PipelineBoardRead(
        jobPostingId=job_posting_id,
        stages=[_serialize_pipeline_stage(stage) for stage in ordered_stages],
    )


def _assert_pipeline_posting_open(posting: JobPosting) -> None:
    if posting.status == JobPostingStatus.CLOSED:
        raise HTTPException(status_code=409, detail="This job opening is closed. Pipeline changes are disabled.")


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
        knockoutRule=requisition.knockoutRule,
        roleSummary=requisition.roleSummary,
        responsibilities=requisition.responsibilities,
        requirementsRich=requisition.requirementsRich,
        benefits=requisition.benefits,
        aboutTeam=requisition.aboutTeam,
        formFields=list(requisition.formFields or []),
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


def _compile_requisition_rules(
    requisition: JobRequisition,
    job_posting_id: str | None,
) -> JobRequisitionRules:
    explicit_skills = [
        skill
        for skill in _unique_normalized(list(requisition.skills or []))
        if not _is_generic_skill_anchor(skill)
    ]
    derived_skills = _derive_skill_anchors(requisition)
    normalized_skills = _unique_normalized([*explicit_skills, *derived_skills])
    min_experience = requisition.minExperience if requisition.minExperience is not None else None
    has_experience_target = min_experience is not None and min_experience > 0
    max_experience_points = MAX_EXPERIENCE_POINTS if has_experience_target else 0
    experience_points_per_year = (
        max(1, MAX_EXPERIENCE_POINTS // int(min_experience))
        if has_experience_target
        else 0
    )
    education_keywords = _education_keywords(requisition.education)
    education_points = MAX_EDUCATION_POINTS if education_keywords else 0
    normalized_certifications = _unique_normalized(list(requisition.certifications or []))
    certification_points = MAX_CERTIFICATION_POINTS if normalized_certifications else 0
    max_skill_points = max(
        0,
        TOTAL_SCORE_POINTS
        - max_experience_points
        - education_points
        - certification_points,
    )
    skill_weights = _distribute_points(max_skill_points, normalized_skills)
    certification_weights = _distribute_points(certification_points, normalized_certifications)
    total_possible_points = TOTAL_SCORE_POINTS
    explicit_knockout_rule = _normalize_optional_knockout_rule(requisition.knockoutRule)
    knockout_rules = {"explicitRule": explicit_knockout_rule}
    scoring_weights = {
        "experiencePointsPerYear": experience_points_per_year,
        "maxExperiencePoints": max_experience_points,
        "maxSkillPoints": max_skill_points,
        "skillWeights": skill_weights,
        "educationPoints": education_points,
        "educationKeywords": education_keywords,
        "certificationWeights": certification_weights,
        "totalPossiblePoints": total_possible_points,
    }
    source_snapshot = {
        "title": requisition.title,
        "departmentId": requisition.departmentId,
        "employmentType": requisition.employmentType.value,
        "skills": list(requisition.skills or []),
        "explicitSkills": explicit_skills,
        "derivedSkills": derived_skills,
        "normalizedSkills": normalized_skills,
        "experienceLevel": requisition.experienceLevel,
        "minExperience": requisition.minExperience,
        "education": requisition.education,
        "certifications": list(requisition.certifications or []),
        "knockoutRule": explicit_knockout_rule,
        "roleSummary": requisition.roleSummary,
        "responsibilities": requisition.responsibilities,
        "requirements": requisition.requirements,
        "requirementsRich": requisition.requirementsRich,
        "compiledFrom": "job_requisition",
    }
    return JobRequisitionRules(
        organizationId=requisition.organizationId,
        requisitionId=requisition.id,
        jobPostingId=job_posting_id,
        rulesVersion=REQUISITION_RULES_VERSION,
        knockoutRules=knockout_rules,
        scoringWeights=scoring_weights,
        sourceSnapshot=source_snapshot,
    )


async def _upsert_requisition_rules(
    repository: JobRequisitionRepository,
    requisition: JobRequisition,
    job_posting_id: str | None,
) -> JobRequisitionRules:
    rules = _compile_requisition_rules(requisition, job_posting_id)
    return await repository.upsert_requisition_rules(rules)


def _serialize_requisition_rules(rules: JobRequisitionRules) -> JobRequisitionRulesRead:
    return JobRequisitionRulesRead(
        id=rules.id,
        organizationId=rules.organizationId,
        requisitionId=rules.requisitionId,
        jobPostingId=rules.jobPostingId,
        rulesVersion=rules.rulesVersion,
        knockoutRules=rules.knockoutRules,
        scoringWeights=rules.scoringWeights,
        sourceSnapshot=rules.sourceSnapshot,
        createdAt=rules.createdAt,
        updatedAt=rules.updatedAt,
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
        formFields=posting.formFields or [],
    )


async def _create_job_posting_for_requisition(
    repository: JobRequisitionRepository,
    requisition: JobRequisition,
) -> JobPosting:
    now = datetime.now(UTC)
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
        formFields=requisition.formFields,
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
        "knockoutRule",
        "roleSummary",
        "responsibilities",
        "requirementsRich",
        "benefits",
        "aboutTeam",
        "formFields",
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
        if field_name == "knockoutRule":
            value = _normalize_optional_knockout_rule(value)
            setattr(requisition, field_name, value)
            changed_fields.append(field_name)
            continue
        if field_name == "formFields":
            value = [f.model_dump() for f in value] if value else None
            setattr(requisition, field_name, value)
            changed_fields.append(field_name)
            continue
        if value is None:
            continue
        if field_name == "title" or field_name == "currency":
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
        requisitions = await repository.list_requisitions(organization_id, raised_by_id=None)
    elif view_scope in {"self", "team", "department", "public_open"}:
        requisition_groups = [
            await repository.list_requisitions(organization_id, raised_by_id=actor_member_id),
            await repository.list_requisitions_by_statuses(
                organization_id,
                OPEN_REQUISITION_STATUSES,
            ),
        ]
        if view_scope == "department":
            department_ids = await _get_member_department_ids(db, actor_member_id)
            requisition_groups.append(
                await repository.list_requisitions(
                    organization_id, department_ids=department_ids
                )
            )
        elif view_scope == "team":
            team_member_ids = await _get_team_member_ids(db, actor_member_id)
            requisition_groups.append(
                await repository.list_requisitions(
                    organization_id, team_member_ids=team_member_ids
                )
            )
        merged = {r.id: r for group in requisition_groups for r in group}
        requisitions = sorted(
            merged.values(),
            key=lambda requisition: requisition.createdAt or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
    else:
        raise HTTPException(status_code=403, detail="you dont have permission")
    return [_serialize_requisition(r, actor_member_id) for r in requisitions]


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
    await _check_single_requisition_access(
        db,
        organization_id,
        actor_member_id,
        view_scope,
        requisition,
        allow_open=True,
    )
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
    _assert_pipeline_posting_open(posting)
    stages = await repository.list_pipeline_stages(organization_id, posting.id)
    next_order = max((stage.order for stage in stages), default=0.0) + 1.0
    stage_type = StageType(body.stageType)
    _assert_single_stage_type(stages, stage_type)
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
        dueDate=body.dueDate,
        extendToNextWorkingDay=body.extendToNextWorkingDay,
    )
    await repository.create_pipeline_stage(stage)
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
    _assert_pipeline_posting_open(posting)
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
    _assert_pipeline_posting_open(target_posting)
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
            dueDate=source_stage.dueDate,
            extendToNextWorkingDay=source_stage.extendToNextWorkingDay,
        )
        await repository.create_pipeline_stage(copied_stage)

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


async def get_requisition_ai_analysis(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    view_scope: str,
    requisition_id: str,
) -> JobRequisitionAiAnalysisRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    await _check_single_requisition_access(
        db,
        organization_id,
        actor_member_id,
        view_scope,
        requisition,
    )

    posting = await repository.get_job_posting_by_requisition(organization_id, requisition_id)
    rules = await repository.get_requisition_rules(organization_id, requisition_id)
    job_posting_id = posting.id if posting is not None else (rules.jobPostingId if rules else None)
    total_applications = await repository.count_applications_for_job_posting(
        organization_id,
        job_posting_id,
    )
    analysis_stats = await repository.list_resume_analysis_stats_for_job_posting(
        organization_id,
        job_posting_id,
    )
    analysis_candidates = await repository.list_resume_analysis_candidates_for_job_posting(
        organization_id,
        job_posting_id,
    )
    completed_scores = [
        score
        for status, score, _flagged in analysis_stats
        if status == "COMPLETED" and score is not None
    ]
    analyzed_count = len(
        [
            status
            for status, _score, _flagged in analysis_stats
            if status in {"TEXT_EXTRACTED", "FLAGGED", "COMPLETED"}
        ]
    )
    flagged_count = len(
        [
            flagged
            for _status, _score, flagged in analysis_stats
            if flagged
        ]
    )

    return JobRequisitionAiAnalysisRead(
        requisitionId=requisition.id,
        jobPostingId=job_posting_id,
        rulesMissing=rules is None,
        rules=_serialize_requisition_rules(rules) if rules is not None else None,
        stats=RequisitionAiAnalysisStatsRead(
            totalApplications=total_applications,
            analyzedApplications=analyzed_count,
            pendingApplications=max(total_applications - analyzed_count, 0),
            flaggedCandidates=flagged_count,
            recommendedCandidates=len(
                [
                    analysis
                    for _application, analysis in analysis_candidates
                    if analysis.compositeScore is not None
                    and analysis.compositeScore >= 70
                    and analysis.evaluationStatus == "QUALIFIED"
                ]
            ),
            averageScore=(
                round(sum(completed_scores) / len(completed_scores), 2)
                if completed_scores
                else None
            ),
        ),
        candidates=[
            RequisitionAiCandidateRead(
                applicationId=application.id,
                candidateId=application.candidateId,
                candidateName=(
                    f"{application.candidate.firstName} {application.candidate.lastName}".strip()
                    if application.candidate is not None
                    else "Candidate"
                ),
                email=application.candidate.email if application.candidate is not None else "",
                aiScore=analysis.compositeScore,
                aiAnalysisStatus=analysis.status,
                evaluationStatus=analysis.evaluationStatus,
                isFlaggedForCheating=bool(analysis.isFlaggedForCheating),
                failedKnockouts=list(analysis.failedKnockouts or []),
            )
            for application, analysis in analysis_candidates
        ],
    )


async def rebuild_requisition_ai_analysis(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    edit_scope: str,
    requisition_id: str,
) -> JobRequisitionAiAnalysisRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    await _check_single_requisition_access(
        db,
        organization_id,
        actor_member_id,
        edit_scope,
        requisition,
    )
    rebuildable_statuses = {
        JobRequisitionStatus.APPROVED,
        JobRequisitionStatus.PUBLISHED,
        JobRequisitionStatus.ACTIVE_HIRING,
        JobRequisitionStatus.FILLED,
        JobRequisitionStatus.CLOSED,
    }
    if requisition.status not in rebuildable_statuses:
        raise HTTPException(
            status_code=400,
            detail="AI screening rules can only be built for approved or active requisitions",
        )

    posting = await repository.get_job_posting_by_requisition(organization_id, requisition_id)
    rules = await _upsert_requisition_rules(
        repository,
        requisition,
        posting.id if posting is not None else None,
    )
    await db.commit()
    await db.refresh(rules)
    return await get_requisition_ai_analysis(
        db=db,
        organization_id=organization_id,
        actor_member_id=actor_member_id,
        view_scope=edit_scope,
        requisition_id=requisition_id,
    )


async def re_evaluate_requisition(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    edit_scope: str,
    requisition_id: str,
    background_tasks: BackgroundTasks,
) -> JobRequisitionAiAnalysisRead:
    repository = JobRequisitionRepository(db)
    requisition = await repository.get_requisition(organization_id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Job requisition not found")
    await _check_single_requisition_access(
        db,
        organization_id,
        actor_member_id,
        edit_scope,
        requisition,
    )
    rebuildable_statuses = {
        JobRequisitionStatus.APPROVED,
        JobRequisitionStatus.PUBLISHED,
        JobRequisitionStatus.ACTIVE_HIRING,
        JobRequisitionStatus.FILLED,
        JobRequisitionStatus.CLOSED,
    }
    if requisition.status not in rebuildable_statuses:
        raise HTTPException(
            status_code=400,
            detail="AI screening rules can only be built for approved or active requisitions",
        )

    posting = await repository.get_job_posting_by_requisition(organization_id, requisition_id)
    rules = await _upsert_requisition_rules(
        repository,
        requisition,
        posting.id if posting is not None else None,
    )

    application_ids = await repository.list_application_ids_for_job_posting(
        organization_id,
        posting.id if posting is not None else None,
    )
    for application_id in application_ids:
        analysis = await create_pending_resume_analysis(
            db=db,
            organization_id=organization_id,
            application_id=application_id,
            resume_url=None,
        )
        analysis.status = "PENDING"
        analysis.lastError = None
        analysis.extractedFacts = None
        analysis.compositeScore = None
        analysis.rawScore = None
        analysis.maxScore = None
        analysis.extractionConfidence = None
        analysis.evaluationStatus = None
        analysis.failedKnockouts = []
        analysis.scoreBreakdown = None

    await db.commit()
    await db.refresh(rules)

    for application_id in application_ids:
        background_tasks.add_task(
            analyze_resume_for_application_task,
            organization_id,
            application_id,
        )

    return await get_requisition_ai_analysis(
        db=db,
        organization_id=organization_id,
        actor_member_id=actor_member_id,
        view_scope=edit_scope,
        requisition_id=requisition_id,
    )


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
        knockoutRule=_normalize_optional_knockout_rule(body.knockoutRule),
        roleSummary=body.roleSummary,
        responsibilities=body.responsibilities,
        requirementsRich=body.requirementsRich,
        benefits=body.benefits,
        aboutTeam=body.aboutTeam,
        formFields=([f.model_dump() for f in body.formFields] if body.formFields else None),
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
    background_tasks: BackgroundTasks | None = None,
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

    if body.customFields is not None and posting.formFields is not None:
        valid_keys = {f["id"] for f in posting.formFields if isinstance(f, dict)}
        for key in body.customFields:
            if key not in valid_keys:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown custom field key: '{key}'. This posting does not have a field with that id.",
                )

    application = CandidateApplication(
        organizationId=posting.organizationId,
        candidateId=candidate.id,
        jobPostingId=posting.id,
        pipelineStageId=default_stage.id,
        source=ApplicationSource.COMPANY_WEBSITE,
        notes=body.coverLetter,
        customFields=body.customFields,
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
    await create_pending_resume_analysis(
        db=db,
        organization_id=posting.organizationId,
        application_id=application.id,
        resume_url=body.resumeUrl,
    )
    await db.commit()

    if background_tasks is not None:
        background_tasks.add_task(
            analyze_resume_for_application_task,
            posting.organizationId,
            application.id,
        )

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
    approval.decidedAt = datetime.now(UTC)

    if any(item.decision == RequisitionApprovalDecision.REJECTED for item in requisition.approvals):
        requisition.status = JobRequisitionStatus.REJECTED
        log_action = "REJECTED"
    elif all(item.decision == RequisitionApprovalDecision.APPROVED for item in requisition.approvals):
        requisition.status = JobRequisitionStatus.APPROVED
        log_action = "APPROVED"
        posting = await _create_job_posting_for_requisition(repository, requisition)
        await _upsert_requisition_rules(repository, requisition, posting.id)
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
    requisition.closedAt = datetime.now(UTC)
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


async def update_job_posting_form_fields(
    db: AsyncSession,
    organization_id: str,
    posting_id: str,
    form_fields: list[dict],
) -> PublicJobPostingListItemRead:
    repository = JobRequisitionRepository(db)
    posting = await repository.get_posting_by_id(posting_id, organization_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    posting.formFields = form_fields
    db.add(posting)
    await db.commit()
    await db.refresh(posting)

    return await _serialize_public_posting(repository, posting)
