from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.resend_service import ResendEmailService
from app.integrations.google.calendar_service import GoogleCalendarService
from app.integrations.google.sheets_service import (
    AnalysisMergeRange,
    GoogleSheetsService,
    SheetValueBlock,
    make_unique_sheet_titles,
    sanitize_sheet_title,
)
from app.models.member import Member
from app.models.recruitment import (
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    CandidateApplicationNote,
    EventStatus,
    InterviewFeedback,
    InterviewFeedbackValue,
    InterviewRejectionRecord,
    InterviewType,
    PipelineStage,
    StageEvaluationCategory,
    StageEvaluationWorkspace,
    StageEvent,
    StageEventParticipant,
    StageType,
)
from app.modules.candidates.repository import CandidatePipelineRepository
from app.modules.candidates.schema import (
    ApplicationInterviewEventRead,
    ApplicationInterviewMeetingRead,
    CandidateApplicationDetailRead,
    CandidateApplicationNoteCreateRequest,
    CandidateApplicationNoteRead,
    CandidateApplicationNoteUpdateRequest,
    CandidateApplicationUpdateRequest,
    CandidateSummaryRead,
    InterviewAcceptRequest,
    InterviewAcceptResponse,
    InterviewerSearchResponse,
    InterviewFeedbackRead,
    InterviewFeedbackValueRead,
    InterviewMeetingCompleteRequest,
    InterviewMeetingCreateRequest,
    InterviewMeetingRead,
    InterviewMeetingUpdateRequest,
    InterviewMoveRequest,
    InterviewMoveResponse,
    InterviewParticipantRead,
    InterviewRejectResponse,
    MoveApplicationStageRequest,
    MyInterviewListResponse,
    MyInterviewRead,
    PipelineApplicationRead,
    PipelineBoardRead,
    PipelineJobPostingRead,
    PipelineStageCreateRequest,
    PipelineStageHistoryRead,
    PipelineStageRead,
    PipelineStageUpdateRequest,
    ReassignmentRequestCreate,
    ReshuffleRequest,
    ReshuffleResponse,
    StageEvaluationCategoryInput,
    StageEvaluationCategoryRead,
    StageEvaluationWorkspaceRead,
    StageInterviewAssignmentInput,
    StageInterviewAssignmentRequest,
    StageInterviewAssignmentResponse,
    StageInterviewWarningRead,
    StageInterviewWarningRequest,
    StageInterviewWarningResponse,
    StageWorkspaceAssignmentRead,
    StageWorkspaceCandidateRead,
    StageWorkspaceInterviewerRead,
    StageWorkspaceRead,
    TeamDistributionRequest,
    TeamDistributionResponse,
)
from app.shared.utils.slugs import generate_unique_slug

DEFAULT_PIPELINE_STAGES: list[dict[str, object]] = [
    {"name": "Applied", "order": 1.0, "color": None, "isDefault": True, "isFinal": False, "stageType": StageType.DEFAULT},
]
STAGE_ORDER_MIN_GAP = 1e-6
LOCKED_ASSIGNMENT_STATUSES = {"ACCEPTED", "SCHEDULED", "COMPLETED"}
ACTIVE_ASSIGNMENT_STATUSES = {"PENDING", "PENDING_ACCEPTANCE", "ACCEPTED", "SCHEDULED"}


@dataclass(frozen=True)
class AnalysisSheetData:
    values: list[list[str]]
    merge_ranges: list[AnalysisMergeRange]


def _is_protected_stage(stage: PipelineStage) -> bool:
    return stage.name.strip().lower() == "applied" and stage.order == 1


async def _generate_stage_slug(
    repository: CandidatePipelineRepository,
    organization_id: str,
    job_posting_id: str,
    name: str,
    excluded_stage_id: str | None = None,
) -> str:
    used_slugs = set(await repository.list_stage_slugs(organization_id, job_posting_id))
    if excluded_stage_id is not None:
        excluded_stage = await repository.get_stage(organization_id, excluded_stage_id)
        if excluded_stage is not None:
            used_slugs.discard(excluded_stage.slug)
    return generate_unique_slug(name, used_slugs, fallback="stage")


def _next_working_day_from_stage(stage: PipelineStage) -> None:
    if stage.dueDate is None:
        raise HTTPException(status_code=400, detail="Due date is not configured for this stage")
    next_date = stage.dueDate + timedelta(days=1)
    while next_date.weekday() == 6:
        next_date += timedelta(days=1)
    stage.dueDate = next_date


def _serialize_category(category: StageEvaluationCategory) -> StageEvaluationCategoryRead:
    return StageEvaluationCategoryRead(
        id=category.id,
        stageId=category.stageId,
        name=category.name,
        type=category.valueType or "NUMERIC",
        maxScore=category.maxScore,
        order=category.order,
    )


def _serialize_workspace(workspace: StageEvaluationWorkspace | None) -> StageEvaluationWorkspaceRead | None:
    if workspace is None:
        return None
    return StageEvaluationWorkspaceRead(
        id=workspace.id,
        stageId=workspace.stageId,
        googleSpreadsheetId=workspace.googleSpreadsheetId,
        googleSpreadsheetUrl=workspace.googleSpreadsheetUrl,
        googleSheetId=workspace.googleSheetId,
        googleSheetTitle=workspace.googleSheetTitle,
        createdByMemberId=workspace.createdByMemberId,
        createdAt=workspace.createdAt,
    )


def _serialize_candidate(candidate: Candidate) -> CandidateSummaryRead:
    return CandidateSummaryRead(
        id=candidate.id,
        firstName=candidate.firstName,
        lastName=candidate.lastName,
        email=candidate.email,
        phone=candidate.phone,
        linkedinUrl=candidate.linkedinUrl,
        portfolioUrl=candidate.portfolioUrl,
        currentCompany=candidate.currentCompany,
        currentTitle=candidate.currentTitle,
        totalExperience=candidate.totalExperience,
        resumeUrl=candidate.resumeUrl,
        image=None,
    )


def _last_moved_at(application: CandidateApplication) -> datetime | None:
    histories = application.__dict__.get("stageHistory", []) or []
    if not histories:
        return None
    return max((history.createdAt for history in histories), default=None)


def _application_status(application: CandidateApplication, stage: PipelineStage) -> str:
    latest_event = _latest_assignment_event(application, stage.id)
    if latest_event is not None:
        return _computed_interview_status(latest_event)
    if stage.stageType == StageType.HIRED:
        return "FINALIZED"
    if stage.stageType == StageType.REJECTED:
        return "REJECTED"
    return "ACTIVE"


def _serialize_application(
    application: CandidateApplication,
    stage: PipelineStage,
) -> PipelineApplicationRead:
    return PipelineApplicationRead(
        id=application.id,
        jobPostingId=application.jobPostingId,
        pipelineStageId=application.pipelineStageId,
        currentStage=stage.name,
        candidate=_serialize_candidate(application.candidate),
        score=application.score,
        rating=application.rating,
        source=application.source,
        appliedDate=application.appliedAt,
        lastMovedAt=_last_moved_at(application),
        status=_application_status(application, stage),
        resumeUrl=application.candidate.resumeUrl,
        interviewMeeting=_serialize_application_interview_meeting(
            _latest_stage_event(application, stage.id)
        ),
        currentAssignment=_serialize_workspace_assignment(
            _latest_assignment_event(application, stage.id)
        ),
    )


def _serialize_stage(stage: PipelineStage) -> PipelineStageRead:
    applications = sorted(
        stage.applications or [],
        key=lambda application: application.appliedAt,
        reverse=True,
    )
    return PipelineStageRead(
        id=stage.id,
        jobPostingId=stage.jobPostingId,
        name=stage.name,
        slug=stage.slug,
        order=stage.order,
        color=stage.color,
        isDefault=stage.isDefault,
        isFinal=stage.isFinal,
        isProtected=_is_protected_stage(stage),
        stageType=stage.stageType.value,
        meetingEnabled=stage.stageType == StageType.INTERVIEW,
        offerLetterEnabled=stage.stageType == StageType.OFFER,
        evaluationEnabled=stage.evaluationEnabled,
        sheetEnabled=stage.sheetEnabled,
        evaluationType=stage.evaluationType,
        evaluationIncludeTotal=stage.evaluationIncludeTotal,
        evaluationIncludeAnalysis=stage.evaluationIncludeAnalysis,
        dueDate=stage.dueDate,
        completedAt=stage.completedAt,
        extendToNextWorkingDay=False,
        evaluationCategories=[
            _serialize_category(category)
            for category in sorted(stage.evaluationCategories or [], key=lambda item: item.order)
        ],
        evaluationWorkspace=_serialize_workspace(stage.evaluationWorkspace),
        applications=[
            _serialize_application(application, stage) for application in applications
        ],
    )


def _serialize_history(history: ApplicationStageHistory) -> PipelineStageHistoryRead:
    moved_by_name = None
    if history.movedBy is not None and history.movedBy.user is not None:
        moved_by_name = history.movedBy.user.name or history.movedBy.user.email

    return PipelineStageHistoryRead(
        id=history.id,
        fromStageId=history.fromStageId,
        fromStageName=history.fromStage.name if history.fromStage is not None else None,
        toStageId=history.toStageId,
        toStageName=history.toStage.name if history.toStage is not None else None,
        movedByMemberId=history.movedByMemberId,
        movedByName=moved_by_name,
        note=history.note,
        createdAt=history.createdAt,
    )


def _serialize_interview_meeting(event: StageEvent) -> InterviewMeetingRead:
    if event.scheduledStartAt is None or event.scheduledEndAt is None:
        raise HTTPException(status_code=400, detail="Interview meeting is missing required metadata")
    return InterviewMeetingRead(
        id=event.id,
        applicationId=event.applicationId,
        stageId=event.stageId,
        title=event.title,
        status=_computed_interview_status(event),
        scheduledStartAt=event.scheduledStartAt,
        scheduledEndAt=event.scheduledEndAt,
        meetingUrl=event.meetingUrl,
        googleCalendarEventId=event.googleCalendarEventId,
        googleCalendarEventUrl=event.googleCalendarEventUrl,
        emailSentAt=event.emailSentAt,
        createdAt=event.createdAt,
    )


def _member_display(member: Member | None) -> tuple[str | None, str | None]:
    if member is None or member.user is None:
        return None, None
    return member.user.name or member.user.email, member.user.email


def _serialize_note(note: CandidateApplicationNote, actor_member_id: str) -> CandidateApplicationNoteRead:
    author_name, author_email = _member_display(note.author)
    return CandidateApplicationNoteRead(
        id=note.id,
        authorMemberId=note.authorMemberId,
        authorName=author_name or "Unknown",
        authorEmail=author_email,
        body=note.body,
        canEdit=note.authorMemberId == actor_member_id,
        createdAt=note.createdAt,
        updatedAt=note.updatedAt,
    )


def _serialize_interview_participant(participant: StageEventParticipant) -> InterviewParticipantRead:
    name, email = _member_display(participant.member)
    return InterviewParticipantRead(
        memberId=participant.memberId,
        name=name or "Unknown",
        email=email,
        role=participant.role,
        isBackup=participant.isBackup,
    )


def _serialize_feedback_value(value: InterviewFeedbackValue) -> InterviewFeedbackValueRead:
    category = value.category
    category_type = category.valueType if category is not None and category.valueType else "NUMERIC"
    display_value: str | float | bool | None
    if category_type == "CHECKBOX":
        display_value = value.booleanValue
    elif category_type == "TEXT":
        display_value = value.textValue
    else:
        display_value = value.numericValue
    return InterviewFeedbackValueRead(
        categoryId=value.categoryId,
        categoryName=category.name if category is not None else "Score",
        categoryType=category_type,
        value=display_value,
    )


def _serialize_feedback(feedback: InterviewFeedback) -> InterviewFeedbackRead:
    name, _email = _member_display(feedback.member)
    return InterviewFeedbackRead(
        id=feedback.id,
        memberId=feedback.memberId,
        memberName=name or "Unknown",
        outcome=feedback.outcome.value if hasattr(feedback.outcome, "value") else str(feedback.outcome),
        score=feedback.score,
        notes=feedback.notes,
        values=[
            _serialize_feedback_value(value)
            for value in sorted(
                feedback.values or [],
                key=lambda item: item.category.order if item.category is not None else 0,
            )
        ],
        createdAt=feedback.createdAt,
    )


def _serialize_interview_event(event: StageEvent) -> ApplicationInterviewEventRead:
    created_by_name, _created_by_email = _member_display(event.createdBy)
    completed_by_name, _completed_by_email = _member_display(event.completedBy)
    duration_minutes = None
    if event.scheduledStartAt is not None and event.scheduledEndAt is not None:
        duration_minutes = max(
            0,
            round((event.scheduledEndAt - event.scheduledStartAt).total_seconds() / 60),
        )
    return ApplicationInterviewEventRead(
        id=event.id,
        stageId=event.stageId,
        stageName=event.stage.name if event.stage is not None else None,
        title=event.title,
        status=_computed_interview_status(event),
        scheduledStartAt=event.scheduledStartAt,
        scheduledEndAt=event.scheduledEndAt,
        completedAt=event.scheduledEndAt if event.status == EventStatus.COMPLETED else None,
        durationMinutes=duration_minutes,
        meetingUrl=event.meetingUrl,
        createdByName=created_by_name,
        completedByName=completed_by_name,
        participants=[
            _serialize_interview_participant(participant)
            for participant in sorted(event.participants or [], key=lambda item: (item.isBackup, item.createdAt))
        ],
        feedbacks=[
            _serialize_feedback(feedback)
            for feedback in sorted(event.feedbacks or [], key=lambda item: item.createdAt)
        ],
        notes=event.notes,
        createdAt=event.createdAt,
    )


def _latest_stage_event(application: CandidateApplication, stage_id: str) -> StageEvent | None:
    events = [
        event
        for event in application.__dict__.get("stageEvents", [])
        if event.stageId == stage_id
        and event.scheduledStartAt is not None
        and event.scheduledEndAt is not None
        and event.status != EventStatus.CANCELLED
    ]
    if not events:
        return None
    return max(events, key=lambda event: event.createdAt or event.scheduledStartAt)


def _computed_interview_status(event: StageEvent | None, now: datetime | None = None) -> str:
    if event is None:
        return "PENDING"
    if event.status == EventStatus.COMPLETED:
        return "COMPLETED"
    if event.status == EventStatus.ONGOING:
        return "ONGOING"
    if event.status == EventStatus.CANCELLED:
        return "CANCELLED"
    if event.status == EventStatus.RESCHEDULED:
        return "RESCHEDULED"
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    current = current.astimezone(UTC)
    start = event.scheduledStartAt
    end = event.scheduledEndAt
    if start is None or end is None:
        return "PENDING"
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if current < start.astimezone(UTC):
        return "PENDING"
    return "ONGOING"


def _serialize_application_interview_meeting(
    event: StageEvent | None,
) -> ApplicationInterviewMeetingRead | None:
    if event is None or event.scheduledStartAt is None or event.scheduledEndAt is None:
        return None
    status = _computed_interview_status(event)
    interviewer_name = None
    completed_by = event.__dict__.get("completedBy")
    created_by = event.__dict__.get("createdBy")
    if status == "COMPLETED" and completed_by is not None and completed_by.__dict__.get("user") is not None:
        user = completed_by.__dict__["user"]
        interviewer_name = user.name or user.email
    elif created_by is not None and created_by.__dict__.get("user") is not None:
        user = created_by.__dict__["user"]
        interviewer_name = user.name or user.email
    return ApplicationInterviewMeetingRead(
        id=event.id,
        status=status,
        scheduledStartAt=event.scheduledStartAt,
        scheduledEndAt=event.scheduledEndAt,
        meetingUrl=event.meetingUrl,
        interviewerName=interviewer_name,
        completedAt=event.scheduledEndAt if status == "COMPLETED" else None,
    )


def _serialize_detail(application: CandidateApplication, actor_member_id: str) -> CandidateApplicationDetailRead:
    histories = sorted(
        application.stageHistory or [],
        key=lambda history: history.createdAt,
        reverse=True,
    )
    return CandidateApplicationDetailRead(
        id=application.id,
        jobPostingId=application.jobPostingId,
        jobPostingTitle=application.jobPosting.title,
        pipelineStageId=application.pipelineStageId,
        currentStage=application.pipelineStage.name,
        candidate=_serialize_candidate(application.candidate),
        source=application.source,
        score=application.score,
        rating=application.rating,
        coverLetter=application.notes,
        internalNotes=application.internalNotes,
        status=_application_status(application, application.pipelineStage),
        resumeUrl=application.candidate.resumeUrl,
        appliedAt=application.appliedAt,
        lastActivityAt=application.lastActivityAt,
        stageHistory=[_serialize_history(history) for history in histories],
        interviewEvents=[
            _serialize_interview_event(event)
            for event in sorted(
                application.stageEvents or [],
                key=lambda item: item.scheduledStartAt or item.createdAt,
                reverse=True,
            )
            if event.scheduledStartAt is not None or event.feedbacks
        ],
        notes=[
            _serialize_note(note, actor_member_id)
            for note in sorted(
                application.internalNoteEntries or [],
                key=lambda item: item.createdAt,
                reverse=True,
            )
        ],
    )


def _serialize_interviewer(member: Member, department: str | None = None) -> StageWorkspaceInterviewerRead:
    user = member.user
    email = getattr(user, "email", None) or ""
    name = getattr(user, "name", None) or email
    return StageWorkspaceInterviewerRead(
        memberId=member.id,
        name=name,
        email=email,
        department=department,
    )


def _latest_assignment_event(application: CandidateApplication, stage_id: str) -> StageEvent | None:
    events = [
        event
        for event in application.__dict__.get("stageEvents", [])
        if event.stageId == stage_id
        and event.participants
        and event.status != EventStatus.CANCELLED
        and any(
            (participant.role == "INTERVIEWER" or participant.role is None)
            and participant.approvalStatus != "REJECTED"
            for participant in event.participants
        )
    ]
    if not events:
        return None
    return max(events, key=lambda event: event.createdAt or event.scheduledStartAt)


def _primary_participant(event: StageEvent) -> StageEventParticipant | None:
    for participant in event.participants or []:
        if participant.role == "INTERVIEWER" or participant.role is None:
            return participant
    return None


def _is_primary_interviewer(event: StageEvent, member_id: str) -> bool:
    participant = _primary_participant(event)
    return (
        participant is not None
        and participant.memberId == member_id
        and participant.approvalStatus != "REJECTED"
    )


def _ensure_self_interview_access(event: StageEvent, member_id: str, access_scope: str | None) -> None:
    if access_scope != "self":
        return
    if not _is_primary_interviewer(event, member_id):
        raise HTTPException(status_code=403, detail="you dont have permission")


def _is_locked_assignment(event: StageEvent | None) -> bool:
    if event is None:
        return False
    if event.status == EventStatus.COMPLETED:
        return True
    participant = _primary_participant(event)
    return participant is not None and participant.approvalStatus in LOCKED_ASSIGNMENT_STATUSES


def _serialize_workspace_assignment(event: StageEvent | None) -> StageWorkspaceAssignmentRead | None:
    if event is None:
        return None
    primary = _primary_participant(event)
    interviewer = None
    if primary is not None and primary.member is not None:
        interviewer = _serialize_interviewer(primary.member)
    status = event.status.value if event.status in {EventStatus.ONGOING, EventStatus.COMPLETED} else (
        primary.approvalStatus if primary is not None else event.status.value
    )
    if status == "PENDING":
        status = "PENDING_ACCEPTANCE"
    return StageWorkspaceAssignmentRead(
        eventId=event.id,
        interviewer=interviewer,
        scheduledStartAt=event.scheduledStartAt,
        scheduledEndAt=event.scheduledEndAt,
        meetLink=event.meetingUrl,
        status=status,
        emailSentAt=event.emailSentAt,
    )


def _serialize_workspace_candidate(
    application: CandidateApplication,
    stage: PipelineStage,
) -> StageWorkspaceCandidateRead:
    return StageWorkspaceCandidateRead(
        applicationId=application.id,
        candidate=_serialize_candidate(application.candidate),
        jobTitle=application.jobPosting.title,
        source=application.source,
        score=application.score,
        rating=application.rating,
        appliedAt=application.appliedAt,
        currentAssignment=_serialize_workspace_assignment(
            _latest_assignment_event(application, stage.id)
        ),
    )


def _serialize_stage_workspace(stage: PipelineStage) -> StageWorkspaceRead:
    applications = sorted(
        stage.applications or [],
        key=lambda application: application.appliedAt,
        reverse=True,
    )
    return StageWorkspaceRead(
        stage=_serialize_stage(stage),
        jobPosting=PipelineJobPostingRead(
            id=stage.jobPosting.id,
            slug=stage.jobPosting.slug,
            title=stage.jobPosting.title,
            status=stage.jobPosting.status.value,
            requisitionId=stage.jobPosting.requisitionId,
        ),
        candidateCount=len(applications),
        candidates=[_serialize_workspace_candidate(application, stage) for application in applications],
    )


async def _ensure_default_stages(
    db: AsyncSession,
    repository: CandidatePipelineRepository,
    organization_id: str,
    job_posting_id: str,
) -> list[PipelineStage]:
    stages = await repository.list_stages_for_job(organization_id, job_posting_id)
    if stages:
        return stages

    new_stages = [
        PipelineStage(
            organizationId=organization_id,
            jobPostingId=job_posting_id,
            name=str(stage["name"]),
            slug=await _generate_stage_slug(repository, organization_id, job_posting_id, str(stage["name"])),
            order=float(stage["order"]),
            color=stage["color"],
            isDefault=bool(stage["isDefault"]),
            isFinal=bool(stage["isFinal"]),
            stageType=stage["stageType"],
            meetingEnabled=bool(stage["stageType"] == StageType.INTERVIEW),
            offerLetterEnabled=bool(stage["stageType"] == StageType.OFFER),
        )
        for stage in DEFAULT_PIPELINE_STAGES
    ]
    db.add_all(new_stages)
    await db.commit()
    return await repository.list_stages_for_job(organization_id, job_posting_id)


async def _normalize_stage_order(db: AsyncSession, stages: list[PipelineStage]) -> None:
    for index, stage in enumerate(stages, start=1):
        stage.order = float(-(index + 1000))
        db.add(stage)
    await db.flush()
    for index, stage in enumerate(stages, start=1):
        stage.order = float(index)
        db.add(stage)
    await db.flush()


def _midpoint_order(previous_order: float | None, next_order: float | None) -> float:
    if previous_order is None and next_order is None:
        return 1.0
    if previous_order is None:
        return next_order - 1.0
    if next_order is None:
        return previous_order + 1.0
    return (previous_order + next_order) / 2.0


async def _ensure_stage_order_gap(
    db: AsyncSession,
    stages: list[PipelineStage],
    previous_order: float | None,
    next_order: float | None,
) -> list[PipelineStage]:
    if previous_order is None or next_order is None:
        return stages
    if abs(next_order - previous_order) > STAGE_ORDER_MIN_GAP:
        return stages
    await _normalize_stage_order(db, sorted(stages, key=lambda item: item.order))
    return sorted(stages, key=lambda item: item.order)


async def _resolve_inserted_stage_order(
    db: AsyncSession,
    stages: list[PipelineStage],
    after_stage_id: str | None,
) -> float:
    ordered_stages = sorted(stages, key=lambda item: item.order)
    if not ordered_stages:
        return 1.0

    if after_stage_id is None:
        return ordered_stages[-1].order + 1.0

    insert_after_index = next((index for index, item in enumerate(ordered_stages) if item.id == after_stage_id), None)
    if insert_after_index is None:
        raise HTTPException(status_code=404, detail="Reference stage not found")

    if insert_after_index == len(ordered_stages) - 1:
        return ordered_stages[insert_after_index].order + 1.0

    for index, stage in enumerate(ordered_stages, start=1):
        stage.order = float(-(index + 1000))
        db.add(stage)
    await db.flush()

    for index, stage in enumerate(ordered_stages, start=1):
        stage.order = float(index if index <= insert_after_index + 1 else index + 1)
        db.add(stage)
    await db.flush()

    return float(insert_after_index + 2)


async def _sync_evaluation_categories(
    db: AsyncSession,
    organization_id: str,
    stage: PipelineStage,
    category_inputs: list[StageEvaluationCategoryInput],
) -> None:
    trimmed_categories = [
        category
        for category in category_inputs
        if category.name.strip()
    ]
    names = [category.name.strip().lower() for category in trimmed_categories]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="Evaluation category names must be unique")

    existing = list(stage.__dict__.get("evaluationCategories", []))
    existing_by_id = {category.id: category for category in existing}
    incoming_ids = {category.id for category in trimmed_categories if category.id is not None}

    for category in existing:
        if category.id not in incoming_ids:
            await db.delete(category)
        else:
            category.order = -(category.order + 1000)
            db.add(category)
    await db.flush()

    for index, category_input in enumerate(trimmed_categories, start=1):
        if category_input.id is not None and category_input.id in existing_by_id:
            category = existing_by_id[category_input.id]
            category.name = category_input.name.strip()
            category.valueType = category_input.type
            category.maxScore = category_input.maxScore
            category.order = index
            db.add(category)
        else:
            db.add(
                StageEvaluationCategory(
                    organizationId=organization_id,
                    stageId=stage.id,
                    name=category_input.name.strip(),
                    valueType=category_input.type,
                    maxScore=category_input.maxScore,
                    order=index,
                )
            )
    await db.flush()


async def _clear_evaluation_categories(db: AsyncSession, stage: PipelineStage) -> None:
    categories = stage.__dict__.get("evaluationCategories", [])
    for category in list(categories):
        await db.delete(category)
    await db.flush()


async def _apply_stage_config(
    db: AsyncSession,
    organization_id: str,
    stage: PipelineStage,
    body: PipelineStageCreateRequest | PipelineStageUpdateRequest,
) -> None:
    next_stage_type = stage.stageType
    if getattr(body, "stageType", None) is not None:
        next_stage_type = StageType(str(body.stageType).strip().upper())
    stage.stageType = next_stage_type
    stage.meetingEnabled = next_stage_type == StageType.INTERVIEW
    stage.offerLetterEnabled = next_stage_type == StageType.OFFER
    stage.isFinal = next_stage_type in {StageType.HIRED, StageType.REJECTED}

    if body.evaluationEnabled is not None:
        stage.evaluationEnabled = body.evaluationEnabled

    if isinstance(body, PipelineStageUpdateRequest) and body.dueDateEnabled is False:
        stage.dueDate = None
    elif body.dueDate is not None:
        stage.dueDate = body.dueDate

    stage.extendToNextWorkingDay = False

    if not stage.evaluationEnabled:
        stage.evaluationType = None
        stage.sheetEnabled = False
        stage.evaluationIncludeTotal = False
        stage.evaluationIncludeAnalysis = False
        await _clear_evaluation_categories(db, stage)
        return

    requested_sheet_enabled = getattr(body, "sheetEnabled", None)
    if requested_sheet_enabled is not None:
        stage.sheetEnabled = bool(requested_sheet_enabled)

    requested_evaluation_type = getattr(body, "evaluationType", None)
    if requested_evaluation_type is not None:
        stage.evaluationType = str(requested_evaluation_type).strip().upper()
    stage.evaluationType = stage.evaluationType or "NUMERIC"
    requested_include_total = getattr(body, "evaluationIncludeTotal", None)
    if requested_include_total is not None:
        stage.evaluationIncludeTotal = bool(requested_include_total)
    requested_include_analysis = getattr(body, "evaluationIncludeAnalysis", None)
    if requested_include_analysis is not None:
        stage.evaluationIncludeAnalysis = bool(requested_include_analysis)
    if stage.evaluationType != "NUMERIC":
        stage.evaluationIncludeTotal = False
    if body.evaluationCategories is not None:
        await _sync_evaluation_categories(db, organization_id, stage, body.evaluationCategories)


async def list_job_postings(
    db: AsyncSession,
    organization_id: str,
) -> list[PipelineJobPostingRead]:
    repository = CandidatePipelineRepository(db)
    postings = await repository.list_job_postings(organization_id)
    return [
        PipelineJobPostingRead(
            id=posting.id,
            slug=posting.slug,
            title=posting.title,
            status=posting.status.value,
            requisitionId=posting.requisitionId,
            candidateCount=len(posting.applications or []),
            stageCount=len(posting.pipelineStages or []),
            priority=posting.requisition.priority if posting.requisition is not None else None,
            openings=posting.requisition.openings if posting.requisition is not None else None,
        )
        for posting in postings
    ]


async def get_pipeline_board(
    db: AsyncSession,
    organization_id: str,
    job_posting_id: str,
) -> PipelineBoardRead:
    repository = CandidatePipelineRepository(db)
    posting = await repository.get_job_posting(organization_id, job_posting_id)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    stages = await _ensure_default_stages(db, repository, organization_id, job_posting_id)
    return PipelineBoardRead(
        jobPostingId=job_posting_id,
        stages=[_serialize_stage(stage) for stage in stages],
    )


async def get_pipeline_board_by_job_slug(
    db: AsyncSession,
    organization_id: str,
    job_slug: str,
) -> PipelineBoardRead:
    repository = CandidatePipelineRepository(db)
    posting = await repository.get_job_posting_by_slug(organization_id, job_slug)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return await get_pipeline_board(db, organization_id, posting.id)


async def move_application_stage(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    actor_user_id: str,
    application_id: str,
    body: MoveApplicationStageRequest,
) -> PipelineApplicationRead:
    repository = CandidatePipelineRepository(db)
    application = await repository.get_application(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    target_stage = await repository.get_stage(organization_id, body.toStageId)
    if target_stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if target_stage.jobPostingId != application.jobPostingId:
        raise HTTPException(status_code=400, detail="Target stage does not belong to this job posting")
    if target_stage.id == application.pipelineStageId:
        return _serialize_application(application, application.pipelineStage)
    current_event = _latest_stage_event(application, application.pipelineStageId)
    if _computed_interview_status(current_event) == "ONGOING":
        raise HTTPException(status_code=400, detail="Candidate cannot be moved while an interview is ongoing")

    from_stage_id = application.pipelineStageId
    application.pipelineStageId = target_stage.id
    history = ApplicationStageHistory(
        organizationId=organization_id,
        applicationId=application.id,
        fromStageId=from_stage_id,
        toStageId=target_stage.id,
        movedByMemberId=actor_member_id,
        note=body.note,
    )
    db.add(application)
    await repository.add_history(history)
    if target_stage.evaluationEnabled and target_stage.sheetEnabled:
        workspace = await _ensure_stage_evaluation_workspace(
            db,
            repository,
            organization_id,
            organization_name,
            actor_member_id,
            actor_user_id,
            target_stage,
        )
        sheets_service = GoogleSheetsService(db)
        values = await sheets_service.get_values(
            actor_user_id,
            workspace.googleSpreadsheetId,
            workspace.googleSheetTitle,
        )
        if application.candidate.email.lower() not in _existing_candidate_emails(values):
            await sheets_service.append_values(
                actor_user_id,
                workspace.googleSpreadsheetId,
                workspace.googleSheetTitle,
                [_stage_candidate_row(target_stage, application, row_number=len(values) + 1)],
            )
        await _update_analysis_sheet(
            db,
            repository,
            sheets_service,
            organization_id,
            actor_user_id,
            target_stage.jobPostingId,
            workspace.googleSpreadsheetId,
        )
    await db.commit()

    refreshed = await repository.get_application(organization_id, application_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize_application(refreshed, target_stage)


async def create_stage(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    actor_user_id: str,
    body: PipelineStageCreateRequest,
) -> PipelineStageRead:
    repository = CandidatePipelineRepository(db)
    posting = await repository.get_job_posting(organization_id, body.jobPostingId)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    stages = await _ensure_default_stages(db, repository, organization_id, body.jobPostingId)
    next_order = await _resolve_inserted_stage_order(db, stages, body.afterStageId)

    new_stage = PipelineStage(
        organizationId=organization_id,
        jobPostingId=body.jobPostingId,
        jobPosting=posting,
        name=body.name.strip(),
        slug=await _generate_stage_slug(repository, organization_id, body.jobPostingId, body.name),
        order=next_order,
        color=None,
        isDefault=False,
        isFinal=body.stageType in {"HIRED", "REJECTED"},
        stageType=StageType(body.stageType),
    )
    await repository.add_stage(new_stage)
    await _apply_stage_config(db, organization_id, new_stage, body)
    await _sync_stage_evaluation_workspace_if_needed(
        db,
        repository,
        organization_id,
        organization_name,
        actor_member_id,
        actor_user_id,
        new_stage,
    )
    await db.commit()
    stages = await repository.list_stages_for_job(organization_id, body.jobPostingId)
    created = next(stage for stage in stages if stage.id == new_stage.id)
    return _serialize_stage(created)


async def update_stage(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    actor_user_id: str,
    stage_id: str,
    body: PipelineStageUpdateRequest,
) -> PipelineStageRead:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage(organization_id, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")

    if body.name is not None:
        stage.name = body.name.strip()
    await _apply_stage_config(db, organization_id, stage, body)
    if body.order is not None:
        stages = await repository.list_stages_for_job(organization_id, stage.jobPostingId)
        other_stages = [item for item in stages if item.id != stage.id]
        previous_order = max((item.order for item in other_stages if item.order < body.order), default=None)
        next_order = min((item.order for item in other_stages if item.order > body.order), default=None)
        stages = await _ensure_stage_order_gap(db, stages, previous_order, next_order)
        stage.order = body.order

    db.add(stage)
    await _sync_stage_evaluation_workspace_if_needed(
        db,
        repository,
        organization_id,
        organization_name,
        actor_member_id,
        actor_user_id,
        stage,
    )
    await db.commit()
    stages = await repository.list_stages_for_job(organization_id, stage.jobPostingId)
    updated = next(item for item in stages if item.id == stage.id)
    return _serialize_stage(updated)


async def extend_stage_due_date(
    db: AsyncSession,
    organization_id: str,
    stage_id: str,
) -> PipelineStageRead:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage(organization_id, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if not stage.extendToNextWorkingDay:
        raise HTTPException(status_code=400, detail="Extension is not enabled for this stage")

    _next_working_day_from_stage(stage)
    db.add(stage)
    await db.commit()
    stages = await repository.list_stages_for_job(organization_id, stage.jobPostingId)
    updated = next(item for item in stages if item.id == stage.id)
    return _serialize_stage(updated)


async def complete_stage(
    db: AsyncSession,
    organization_id: str,
    stage_id: str,
) -> PipelineStageRead:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage(organization_id, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if stage.completedAt is not None:
        raise HTTPException(status_code=409, detail="Stage is already completed")
    stage.completedAt = datetime.now(UTC)
    db.add(stage)
    await db.commit()
    stages = await repository.list_stages_for_job(organization_id, stage.jobPostingId)
    updated = next(item for item in stages if item.id == stage.id)
    return _serialize_stage(updated)


async def reopen_stage(
    db: AsyncSession,
    organization_id: str,
    stage_id: str,
) -> PipelineStageRead:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage(organization_id, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if stage.completedAt is None:
        raise HTTPException(status_code=409, detail="Stage is not completed")
    stage.completedAt = None
    db.add(stage)
    await db.commit()
    stages = await repository.list_stages_for_job(organization_id, stage.jobPostingId)
    updated = next(item for item in stages if item.id == stage.id)
    return _serialize_stage(updated)


async def delete_stage(
    db: AsyncSession,
    organization_id: str,
    stage_id: str,
) -> None:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage(organization_id, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if _is_protected_stage(stage):
        raise HTTPException(status_code=400, detail="Applied stage cannot be deleted")
    application_count = await repository.count_stage_applications(organization_id, stage_id)
    if application_count > 0:
        raise HTTPException(status_code=400, detail="Move candidates out of this stage before deleting it")
    history_count = await repository.count_stage_history(organization_id, stage_id)
    if history_count > 0:
        raise HTTPException(status_code=400, detail="Stages with movement history cannot be deleted")

    job_posting_id = stage.jobPostingId
    await db.delete(stage)
    await db.flush()
    stages = await repository.list_stages_for_job(organization_id, job_posting_id)
    await _normalize_stage_order(db, sorted(stages, key=lambda item: item.order))
    await db.commit()


async def get_application_detail(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    application_id: str,
) -> CandidateApplicationDetailRead:
    repository = CandidatePipelineRepository(db)
    application = await repository.get_application_detail(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize_detail(application, actor_member_id)


async def get_stage_workspace(
    db: AsyncSession,
    organization_id: str,
    stage_slug: str,
) -> StageWorkspaceRead:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage_by_slug(organization_id, stage_slug)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if stage.stageType != StageType.INTERVIEW:
        raise HTTPException(status_code=409, detail="Only interview stages have a workspace")
    return _serialize_stage_workspace(stage)


async def get_stage_workspace_by_job_slug(
    db: AsyncSession,
    organization_id: str,
    job_slug: str,
    stage_slug: str,
) -> StageWorkspaceRead:
    repository = CandidatePipelineRepository(db)
    posting = await repository.get_job_posting_by_slug(organization_id, job_slug)
    if posting is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    stage = await repository.get_stage_by_job_and_slug(organization_id, posting.id, stage_slug)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if stage.stageType != StageType.INTERVIEW:
        raise HTTPException(status_code=409, detail="Only interview stages have a workspace")
    return _serialize_stage_workspace(stage)


async def search_interviewers(
    db: AsyncSession,
    organization_id: str,
    search: str | None,
) -> InterviewerSearchResponse:
    repository = CandidatePipelineRepository(db)
    rows = await repository.search_interviewers(organization_id, search, limit=20)
    return InterviewerSearchResponse(
        items=[_serialize_interviewer(member, department) for member, department in rows]
    )


async def update_candidate_application(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    application_id: str,
    body: CandidateApplicationUpdateRequest,
) -> CandidateApplicationDetailRead:
    repository = CandidatePipelineRepository(db)
    application = await repository.get_application_detail(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    if body.internalNotes is not None:
        application.internalNotes = body.internalNotes.strip() or None
    if body.rating is not None:
        application.rating = body.rating
    if body.resumeUrl is not None:
        application.candidate.resumeUrl = body.resumeUrl.strip() or None

    db.add(application)
    db.add(application.candidate)
    await db.commit()

    refreshed = await repository.get_application_detail(organization_id, application_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize_detail(refreshed, actor_member_id)


async def create_application_note(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    application_id: str,
    body: CandidateApplicationNoteCreateRequest,
) -> CandidateApplicationDetailRead:
    repository = CandidatePipelineRepository(db)
    application = await repository.get_application_detail(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    note = CandidateApplicationNote(
        organizationId=organization_id,
        applicationId=application_id,
        authorMemberId=actor_member_id,
        body=body.body.strip(),
    )
    await repository.add_application_note(note)
    await db.commit()
    refreshed = await repository.get_application_detail(organization_id, application_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize_detail(refreshed, actor_member_id)


async def update_application_note(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    application_id: str,
    note_id: str,
    body: CandidateApplicationNoteUpdateRequest,
) -> CandidateApplicationDetailRead:
    repository = CandidatePipelineRepository(db)
    note = await repository.get_application_note(organization_id, application_id, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.authorMemberId != actor_member_id:
        raise HTTPException(status_code=403, detail="you dont have permission")
    note.body = body.body.strip()
    db.add(note)
    await db.commit()
    refreshed = await repository.get_application_detail(organization_id, application_id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _serialize_detail(refreshed, actor_member_id)


def _assignment_date(value: datetime) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    ist = value.astimezone(UTC) + timedelta(hours=5, minutes=30)
    return ist.date()


async def _build_assignment_warnings(
    repository: CandidatePipelineRepository,
    organization_id: str,
    assignments: list[StageInterviewAssignmentInput],
) -> list[StageInterviewWarningRead]:
    scheduled_assignments = [assignment for assignment in assignments if assignment.scheduledStartAt is not None]
    if not scheduled_assignments:
        return []
    member_ids = list({assignment.interviewerMemberId for assignment in scheduled_assignments})
    target_dates = list({
        _assignment_date(assignment.scheduledStartAt)
        for assignment in scheduled_assignments
        if assignment.scheduledStartAt is not None
    })
    leave_requests = await repository.list_approved_leave_for_members(
        organization_id,
        member_ids,
        target_dates,
    )
    holidays = await repository.list_holidays(organization_id, target_dates)

    leave_pairs = {
        (leave.memberId, target_date)
        for leave in leave_requests
        for target_date in target_dates
        if leave.startDate <= target_date <= leave.endDate
    }
    holidays_by_date = {holiday.holidayDate: holiday for holiday in holidays}

    # Count existing interviews per member per date
    interview_counts: dict[tuple[str, date], int] = {}
    for assignment in scheduled_assignments:
        if assignment.scheduledStartAt is None:
            continue
        target_date = _assignment_date(assignment.scheduledStartAt)
        key = (assignment.interviewerMemberId, target_date)
        if key not in interview_counts:
            interview_counts[key] = await repository.count_interviews_for_member_on_date(
                organization_id, assignment.interviewerMemberId, target_date
            )

    warnings: list[StageInterviewWarningRead] = []
    for assignment in scheduled_assignments:
        if assignment.scheduledStartAt is None:
            continue
        target_date = _assignment_date(assignment.scheduledStartAt)
        messages: list[str] = []
        if target_date.weekday() == 6:
            messages.append("Selected date is a Sunday.")
        if target_date in holidays_by_date:
            messages.append(f"{holidays_by_date[target_date].name} is marked as a holiday.")
        if (assignment.interviewerMemberId, target_date) in leave_pairs:
            messages.append("Interviewer is on approved leave on this date.")
        existing_count = interview_counts.get((assignment.interviewerMemberId, target_date), 0)
        if existing_count >= 3:
            messages.append(f"Interviewer already has {existing_count} interviews scheduled on this date.")
        elif existing_count > 0:
            messages.append(f"Interviewer already has {existing_count} interview(s) scheduled on this date.")
        if messages:
            warnings.append(
                StageInterviewWarningRead(
                    applicationId=assignment.applicationId,
                    interviewerMemberId=assignment.interviewerMemberId,
                    messages=messages,
                )
            )
    return warnings


async def preview_stage_interview_warnings(
    db: AsyncSession,
    organization_id: str,
    stage_slug: str,
    body: StageInterviewWarningRequest,
) -> StageInterviewWarningResponse:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage_by_slug(organization_id, stage_slug)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if body.jobPostingId and stage.jobPostingId != body.jobPostingId:
        raise HTTPException(status_code=400, detail="Stage does not belong to the specified job posting")
    warnings = await _build_assignment_warnings(repository, organization_id, body.assignments)
    return StageInterviewWarningResponse(warnings=warnings)


async def assign_stage_interviews(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    stage_slug: str,
    body: StageInterviewAssignmentRequest,
) -> StageInterviewAssignmentResponse:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage_by_slug(organization_id, stage_slug)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if body.jobPostingId and stage.jobPostingId != body.jobPostingId:
        raise HTTPException(status_code=400, detail="Stage does not belong to the specified job posting")
    if stage.stageType != StageType.INTERVIEW:
        raise HTTPException(status_code=400, detail="Assignments can only be created for interview stages")
    if stage.completedAt is not None:
        raise HTTPException(status_code=409, detail="Cannot assign interviews in a completed stage")

    applications_by_id = {application.id: application for application in stage.applications}
    member_ids = list({
        member_id
        for assignment in body.assignments
        for member_id in [assignment.interviewerMemberId, *assignment.backupInterviewers]
    })
    members = await repository.get_members_by_ids(organization_id, member_ids)
    members_by_id = {member.id: member for member in members}
    missing_member_ids = [member_id for member_id in member_ids if member_id not in members_by_id]
    if missing_member_ids:
        raise HTTPException(status_code=400, detail="One or more interviewers were not found")

    warnings = await _build_assignment_warnings(repository, organization_id, body.assignments)
    email_service = ResendEmailService()

    for assignment in body.assignments:
        application = applications_by_id.get(assignment.applicationId)
        if application is None:
            raise HTTPException(status_code=400, detail="One or more candidates are not in this stage")
        if _is_locked_assignment(_latest_assignment_event(application, stage.id)):
            raise HTTPException(status_code=409, detail="Accepted or scheduled assignments cannot be overwritten")

        interviewer = members_by_id[assignment.interviewerMemberId]
        interviewer_email = interviewer.user.email if interviewer.user is not None else None
        if not interviewer_email:
            raise HTTPException(status_code=400, detail="Interviewer email is missing")

        starts_at = assignment.scheduledStartAt
        if starts_at is not None:
            if starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=UTC)
            starts_at = starts_at.astimezone(UTC)
        ends_at = starts_at + timedelta(minutes=assignment.durationMinutes) if starts_at is not None else None
        candidate_name = _candidate_display_name(application)
        interviewer_name = interviewer.user.name or interviewer.user.email

        existing_event = await repository.get_latest_stage_event(
            organization_id,
            application.id,
            stage.id,
        )
        is_reassignment = existing_event is not None and existing_event.status in {
            EventStatus.SCHEDULED,
            EventStatus.RESCHEDULED,
        }

        event = existing_event or StageEvent(
            organizationId=organization_id,
            applicationId=application.id,
            stageId=stage.id,
            createdByMemberId=actor_member_id,
            title=f"{stage.name} interview - {candidate_name}",
            description=f"Interview for {application.jobPosting.title}",
            interviewType=InterviewType.OTHER,
        )
        event.title = f"{stage.name} interview - {candidate_name}"
        event.description = f"Interview for {application.jobPosting.title}"
        event.interviewType = InterviewType.OTHER
        event.assignmentMode = "DIRECT"
        event.teamId = None
        event.status = EventStatus.RESCHEDULED if is_reassignment and starts_at is not None else EventStatus.SCHEDULED
        event.scheduledStartAt = starts_at
        event.scheduledEndAt = ends_at
        event.meetingUrl = assignment.meetLink or None

        if existing_event is None:
            await repository.add_stage_event(event)
        else:
            for participant in list(existing_event.participants or []):
                await db.delete(participant)
            await db.flush()

        await repository.add_stage_event_participant(
            StageEventParticipant(
                eventId=event.id,
                memberId=interviewer.id,
                role="INTERVIEWER",
                isBackup=False,
                approvalStatus="PENDING_ACCEPTANCE",
            )
        )
        for backup_member_id in dict.fromkeys(assignment.backupInterviewers):
            if backup_member_id == interviewer.id:
                continue
            await repository.add_stage_event_participant(
                StageEventParticipant(
                    eventId=event.id,
                    memberId=backup_member_id,
                    role="BACKUP",
                    isBackup=True,
                    approvalStatus="PENDING_ACCEPTANCE",
                )
            )

        starts_at_text = _meeting_time_text(starts_at) if starts_at is not None else "To be scheduled after you accept"
        await email_service.send_stage_interview_assignment_to_interviewer(
            to_email=interviewer_email,
            interviewer_name=interviewer_name,
            candidate_name=candidate_name,
            candidate_email=application.candidate.email,
            stage_name=stage.name,
            organization_name=organization_name,
            starts_at_text=starts_at_text,
        )
        if starts_at is not None:
            await email_service.send_stage_interview_assignment_to_candidate(
                to_email=application.candidate.email,
                candidate_name=candidate_name,
                interviewer_name=interviewer_name,
                organization_name=organization_name,
                starts_at_text=starts_at_text,
            )
        event.emailSentAt = datetime.now(UTC)
        db.add(event)

    await db.commit()
    return StageInterviewAssignmentResponse(
        assignedCount=len(body.assignments),
        warnings=warnings,
    )


async def distribute_stage_interviews(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    stage_slug: str,
    body: TeamDistributionRequest,
) -> TeamDistributionResponse:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage_by_slug(organization_id, stage_slug)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if stage.completedAt is not None:
        raise HTTPException(status_code=409, detail="Cannot distribute interviews in a completed stage")

    team = await repository.get_hiring_team(organization_id, body.hiringTeamId)
    if team is None:
        raise HTTPException(status_code=404, detail="Hiring team not found")
    if team.jobPostingId != stage.jobPostingId:
        raise HTTPException(status_code=400, detail="Hiring team does not belong to this job posting")

    team_member_ids = [item.memberId for item in (team.members or [])]
    if not team_member_ids:
        raise HTTPException(status_code=400, detail="Hiring team has no members")

    applications_by_id = {application.id: application for application in stage.applications}
    selected_applications = []
    for app_id in body.applicationIds:
        application = applications_by_id.get(app_id)
        if application is None:
            raise HTTPException(status_code=400, detail="One or more candidates are not in this stage")
        if _is_locked_assignment(_latest_assignment_event(application, stage.id)):
            continue
        selected_applications.append(application)
    if not selected_applications:
        return TeamDistributionResponse(assignedCount=0, warnings=[])

    # Build round-robin assignments
    assignments: list[StageInterviewAssignmentInput] = []
    for index, application in enumerate(selected_applications):
        interviewer_member_id = team_member_ids[index % len(team_member_ids)]
        assignments.append(
            StageInterviewAssignmentInput(
                applicationId=application.id,
                interviewerMemberId=interviewer_member_id,
                scheduledStartAt=body.scheduledStartAt,
                durationMinutes=body.durationMinutes,
                backupInterviewers=body.backupInterviewers,
            )
        )

    warnings = await _build_assignment_warnings(repository, organization_id, assignments)
    if warnings and not body.ignoreWarnings:
        return TeamDistributionResponse(assignedCount=0, warnings=warnings)

    backup_member_ids = list(dict.fromkeys(body.backupInterviewers or []))
    members = await repository.get_members_by_ids(
        organization_id,
        list(dict.fromkeys([*team_member_ids, *backup_member_ids])),
    )
    members_by_id = {member.id: member for member in members}

    email_service = ResendEmailService()

    for assignment in assignments:
        application = applications_by_id[assignment.applicationId]
        interviewer = members_by_id[assignment.interviewerMemberId]
        interviewer_email = interviewer.user.email if interviewer.user is not None else None
        if not interviewer_email:
            raise HTTPException(status_code=400, detail="Interviewer email is missing")

        starts_at = assignment.scheduledStartAt
        if starts_at is not None:
            if starts_at.tzinfo is None:
                starts_at = starts_at.replace(tzinfo=UTC)
            starts_at = starts_at.astimezone(UTC)
        ends_at = starts_at + timedelta(minutes=assignment.durationMinutes) if starts_at is not None else None
        candidate_name = _candidate_display_name(application)
        interviewer_name = interviewer.user.name or interviewer.user.email

        event = StageEvent(
            organizationId=organization_id,
            applicationId=application.id,
            stageId=stage.id,
            createdByMemberId=actor_member_id,
            title=f"{stage.name} interview - {candidate_name}",
            description=f"Interview for {application.jobPosting.title}",
            interviewType=InterviewType.OTHER,
            status=EventStatus.SCHEDULED,
            scheduledStartAt=starts_at,
            scheduledEndAt=ends_at,
        )
        await repository.add_stage_event(event)
        await repository.add_stage_event_participant(
            StageEventParticipant(
                eventId=event.id,
                memberId=interviewer.id,
                role="INTERVIEWER",
                isBackup=False,
                approvalStatus="PENDING_ACCEPTANCE",
            )
        )

        # Add backup interviewers if any
        for backup_member_id in (body.backupInterviewers or []):
            if backup_member_id == assignment.interviewerMemberId:
                continue
            backup_member = members_by_id.get(backup_member_id)
            if backup_member is not None:
                await repository.add_stage_event_participant(
                    StageEventParticipant(
                        eventId=event.id,
                        memberId=backup_member_id,
                        role="BACKUP",
                        isBackup=True,
                        approvalStatus="PENDING",
                    )
                )

        starts_at_text = _meeting_time_text(starts_at) if starts_at is not None else "To be scheduled after you accept"
        await email_service.send_stage_interview_assignment_to_interviewer(
            to_email=interviewer_email,
            interviewer_name=interviewer_name,
            candidate_name=candidate_name,
            candidate_email=application.candidate.email,
            stage_name=stage.name,
            organization_name=organization_name,
            starts_at_text=starts_at_text,
        )
        if starts_at is not None:
            await email_service.send_stage_interview_assignment_to_candidate(
                to_email=application.candidate.email,
                candidate_name=candidate_name,
                interviewer_name=interviewer_name,
                organization_name=organization_name,
                starts_at_text=starts_at_text,
            )
        event.emailSentAt = datetime.now(UTC)
        db.add(event)

    await db.commit()
    return TeamDistributionResponse(
        assignedCount=len(assignments),
        warnings=warnings,
    )


async def reshuffle_interview_assignment(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    application_id: str,
    event_id: str,
    body: ReshuffleRequest,
) -> ReshuffleResponse:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_with_participants(organization_id, event_id)
    if event is None or event.applicationId != application_id:
        raise HTTPException(status_code=404, detail="Interview event not found")
    if event.stage is not None and event.stage.completedAt is not None:
        raise HTTPException(status_code=409, detail="Cannot reshuffle in a completed stage")

    if body.newInterviewerMemberId is not None:
        # Manual reshuffle
        new_interviewer = await repository.get_member(organization_id, body.newInterviewerMemberId)
        if new_interviewer is None:
            raise HTTPException(status_code=400, detail="New interviewer not found")
        new_member_id = new_interviewer.id
    else:
        # Auto reshuffle: find next available team member with fewest warnings
        # For simplicity, find any org member who is not the current primary and has no warnings
        current_primary = None
        for p in (event.participants or []):
            if p.role == "INTERVIEWER" or p.role is None:
                current_primary = p
                break

        if current_primary is None:
            raise HTTPException(status_code=400, detail="No primary interviewer to reshuffle")

        rejected_member_ids = await repository.list_rejected_member_ids_for_event(organization_id, event.id)
        backup_participants = [
            p
            for p in (event.participants or [])
            if p.role == "BACKUP"
            and p.memberId not in rejected_member_ids
            and p.approvalStatus != "REJECTED"
        ]
        active_counts = await repository.count_active_interviews_for_members(
            organization_id,
            [p.memberId for p in backup_participants],
        )
        promoted_backup = min(
            backup_participants,
            key=lambda p: (active_counts.get(p.memberId, 0), p.createdAt),
            default=None,
        )
        new_member_id = promoted_backup.memberId if promoted_backup is not None else None

        if new_member_id is None:
            raise HTTPException(status_code=400, detail="No backup interviewer available for auto-reshuffle")

    # Swap primary interviewer
    for p in (event.participants or []):
        if p.role == "INTERVIEWER" or p.role is None:
            p.role = "BACKUP"
            p.isBackup = True
        elif p.memberId == new_member_id:
            p.role = "INTERVIEWER"
            p.isBackup = False
            p.approvalStatus = "PENDING_ACCEPTANCE"

    db.add(event)
    await db.commit()

    # Build minimal warning for the new interviewer
    assignment_input = StageInterviewAssignmentInput(
        applicationId=application_id,
        interviewerMemberId=new_member_id,
        scheduledStartAt=event.scheduledStartAt,
        durationMinutes=30,
    )
    warnings = await _build_assignment_warnings(repository, organization_id, [assignment_input])

    # Send reassignment email
    new_interviewer_member = await repository.get_member(organization_id, new_member_id)
    if new_interviewer_member is not None and new_interviewer_member.user is not None:
        email_service = ResendEmailService()
        candidate_name = _candidate_display_name(event.application)
        await email_service.send_stage_interview_assignment_to_interviewer(
            to_email=new_interviewer_member.user.email,
            interviewer_name=new_interviewer_member.user.name or new_interviewer_member.user.email,
            candidate_name=candidate_name,
            candidate_email=event.application.candidate.email,
            stage_name=event.stage.name,
            organization_name=organization_name,
            starts_at_text=_meeting_time_text(event.scheduledStartAt),
        )

    return ReshuffleResponse(
        eventId=event.id,
        newInterviewerMemberId=new_member_id,
        warnings=warnings,
    )


async def move_interview_assignment(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    application_id: str,
    event_id: str,
    body: InterviewMoveRequest,
) -> InterviewMoveResponse:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_with_participants(organization_id, event_id)
    if event is None or event.applicationId != application_id:
        raise HTTPException(status_code=404, detail="Interview event not found")
    if event.stage is not None and event.stage.completedAt is not None:
        raise HTTPException(status_code=409, detail="Cannot move assignments in a completed stage")

    new_interviewer = await repository.get_member(organization_id, body.newInterviewerMemberId)
    if new_interviewer is None:
        raise HTTPException(status_code=400, detail="New interviewer not found")
    if new_interviewer.user is None or not new_interviewer.user.email:
        raise HTTPException(status_code=400, detail="New interviewer email is missing")

    # Find current primary interviewer and remove them
    old_primary = None
    for p in (event.participants or []):
        if p.role == "INTERVIEWER" or p.role is None:
            old_primary = p
            break

    if old_primary is not None:
        await db.delete(old_primary)
        await db.flush()

    # Add new primary interviewer with PENDING_ACCEPTANCE
    new_participant = StageEventParticipant(
        eventId=event.id,
        memberId=new_interviewer.id,
        role="INTERVIEWER",
        isBackup=False,
        approvalStatus="PENDING_ACCEPTANCE",
    )
    await repository.add_stage_event_participant(new_participant)

    candidate_name = _candidate_display_name(event.application)
    interviewer_name = new_interviewer.user.name or new_interviewer.user.email

    # Send approval request email to the new interviewer (not the candidate yet)
    email_service = ResendEmailService()
    starts_at_text = _meeting_time_text(event.scheduledStartAt) if event.scheduledStartAt is not None else "To be scheduled after you accept"
    await email_service.send_stage_interview_assignment_to_interviewer(
        to_email=new_interviewer.user.email,
        interviewer_name=interviewer_name,
        candidate_name=candidate_name,
        candidate_email=event.application.candidate.email,
        stage_name=event.stage.name,
        organization_name=organization_name,
        starts_at_text=starts_at_text,
    )

    db.add(event)
    await db.commit()

    return InterviewMoveResponse(
        eventId=event.id,
        newInterviewerMemberId=new_interviewer.id,
        status="PENDING_ACCEPTANCE",
    )


async def accept_interview(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    member_id: str,
    actor_user_id: str,
    event_id: str,
    body: InterviewAcceptRequest,
) -> InterviewAcceptResponse:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_with_participants(organization_id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Interview event not found")

    participant = next(
        (
            item
            for item in (event.participants or [])
            if item.memberId == member_id and (item.role == "INTERVIEWER" or item.role is None)
        ),
        None,
    )
    if participant is None:
        raise HTTPException(status_code=400, detail="You are not the primary interviewer for this assignment")
    if participant.approvalStatus == "REJECTED":
        raise HTTPException(status_code=400, detail="Rejected assignments cannot be accepted")

    now = datetime.now(UTC)
    meeting: InterviewMeetingRead | None = None
    participant.approvedAt = now

    if body.scheduledStartAt is not None:
        starts_at = body.scheduledStartAt
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=UTC)
        starts_at = starts_at.astimezone(UTC)
        if starts_at < now:
            raise HTTPException(status_code=400, detail="Interview cannot be scheduled in the past")
        if event.stage is not None and event.stage.dueDate is not None:
            due_date = event.stage.dueDate
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=UTC)
            if starts_at > due_date.astimezone(UTC):
                raise HTTPException(status_code=400, detail="Interview cannot be scheduled after the stage due date")

        warnings = await _build_assignment_warnings(
            repository,
            organization_id,
            [
                StageInterviewAssignmentInput(
                    applicationId=event.applicationId,
                    interviewerMemberId=member_id,
                    scheduledStartAt=starts_at,
                    durationMinutes=body.durationMinutes,
                )
            ],
        )
        if any(
            "approved leave" in message.lower()
            for warning in warnings
            for message in warning.messages
        ):
            raise HTTPException(status_code=400, detail="Interviewer is on approved leave at the selected time")

        participant.approvalStatus = "SCHEDULED"
        participant.scheduledTime = starts_at
        db.add(participant)
        meeting = await create_interview_meeting(
            db,
            organization_id,
            member_id,
            actor_user_id,
            event.applicationId,
            InterviewMeetingCreateRequest(
                mode="SCHEDULE",
                scheduledStartAt=starts_at,
                durationMinutes=body.durationMinutes,
            ),
        )
        if event.status == EventStatus.COMPLETED and meeting.id != event.id:
            db.add(
                StageEventParticipant(
                    eventId=meeting.id,
                    memberId=member_id,
                    role="INTERVIEWER",
                    approvalStatus="SCHEDULED",
                    approvedAt=now,
                    scheduledTime=starts_at,
                )
            )
            await db.commit()
    else:
        participant.approvalStatus = "ACCEPTED"
        db.add(participant)
        await db.commit()

    # Send reassignment email to candidate if the interviewer accepted with a time
    if participant.approvalStatus == "SCHEDULED" and event.scheduledStartAt is not None:
        candidate = event.application.candidate
        candidate_email = candidate.email
        candidate_name = _candidate_display_name(event.application)
        interviewer_name = None
        if participant.member is not None and participant.member.user is not None:
            interviewer_name = participant.member.user.name or participant.member.user.email
        if candidate_email and interviewer_name:
            email_service = ResendEmailService()
            await email_service.send_stage_interview_assignment_to_candidate(
                to_email=candidate_email,
                candidate_name=candidate_name,
                interviewer_name=interviewer_name,
                organization_name=organization_name,
                starts_at_text=_meeting_time_text(event.scheduledStartAt),
            )

    return InterviewAcceptResponse(
        eventId=event_id,
        status=participant.approvalStatus,
        meeting=meeting,
    )


async def reject_interview(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    member_id: str,
    event_id: str,
) -> InterviewRejectResponse:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_with_participants(organization_id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Interview event not found")

    participant = next(
        (
            item
            for item in (event.participants or [])
            if item.memberId == member_id and (item.role == "INTERVIEWER" or item.role is None)
        ),
        None,
    )
    if participant is None:
        raise HTTPException(status_code=400, detail="You are not the primary interviewer for this assignment")

    now = datetime.now(UTC)
    participant.approvalStatus = "REJECTED"
    participant.rejectedAt = now
    participant.role = "BACKUP"
    participant.isBackup = True
    db.add(participant)

    rejected_member_ids = await repository.list_rejected_member_ids_for_event(organization_id, event.id)
    if member_id not in rejected_member_ids:
        await repository.add_interview_rejection_record(
            InterviewRejectionRecord(
                organizationId=organization_id,
                eventId=event.id,
                memberId=member_id,
                rejectedAt=now,
            )
        )
        rejected_member_ids.add(member_id)

    candidate_backups = [
        item
        for item in (event.participants or [])
        if item.role == "BACKUP"
        and item.memberId not in rejected_member_ids
        and item.approvalStatus != "REJECTED"
    ]
    if not candidate_backups:
        event.status = EventStatus.CANCELLED
        db.add(event)
        await db.commit()
        return InterviewRejectResponse(
            eventId=event.id,
            newInterviewerMemberId=None,
            status="UNASSIGNED",
            warnings=[],
        )

    active_counts = await repository.count_active_interviews_for_members(
        organization_id,
        [item.memberId for item in candidate_backups],
    )
    promoted = min(
        candidate_backups,
        key=lambda item: (active_counts.get(item.memberId, 0), item.createdAt),
    )
    promoted.role = "INTERVIEWER"
    promoted.isBackup = False
    promoted.approvalStatus = "PENDING_ACCEPTANCE"
    promoted.approvedAt = None
    promoted.rejectedAt = None
    db.add(promoted)
    event.status = EventStatus.RESCHEDULED
    db.add(event)
    await db.commit()

    warnings: list[StageInterviewWarningRead] = []
    if event.scheduledStartAt is not None:
        warnings = await _build_assignment_warnings(
            repository,
            organization_id,
            [
                StageInterviewAssignmentInput(
                    applicationId=event.applicationId,
                    interviewerMemberId=promoted.memberId,
                    scheduledStartAt=event.scheduledStartAt,
                    durationMinutes=30,
                )
            ],
        )

    if promoted.member is not None and promoted.member.user is not None:
        email_service = ResendEmailService()
        candidate_name = _candidate_display_name(event.application)
        starts_at_text = _meeting_time_text(event.scheduledStartAt) if event.scheduledStartAt else "To be scheduled"
        await email_service.send_stage_interview_assignment_to_interviewer(
            to_email=promoted.member.user.email,
            interviewer_name=promoted.member.user.name or promoted.member.user.email,
            candidate_name=candidate_name,
            candidate_email=event.application.candidate.email,
            stage_name=event.stage.name if event.stage else "Interview",
            organization_name=organization_name,
            starts_at_text=starts_at_text,
        )

    return InterviewRejectResponse(
        eventId=event.id,
        newInterviewerMemberId=promoted.memberId,
        status="ESCALATED",
        warnings=warnings,
    )


async def list_my_interviews(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
) -> MyInterviewListResponse:
    repository = CandidatePipelineRepository(db)
    rows = await repository.list_my_interviews(organization_id, member_id)
    items: list[MyInterviewRead] = []
    for participant in rows:
        event = participant.event
        if event is None:
            continue
        application = event.application
        if application is None:
            continue
        candidate = application.candidate
        stage = event.stage
        is_backup = participant.role == "BACKUP" and participant.approvalStatus != "REJECTED"
        status = participant.approvalStatus
        if status == "PENDING":
            status = "PENDING_ACCEPTANCE"
        if status in {"PENDING_ACCEPTANCE", "ACCEPTED", "REJECTED"}:
            display_status = status
        elif status == "SCHEDULED":
            computed_status = _computed_interview_status(event)
            display_status = "SCHEDULED" if computed_status == "PENDING" else computed_status
        else:
            display_status = _computed_interview_status(event)
        items.append(
            MyInterviewRead(
                eventId=event.id,
                applicationId=application.id,
                stageId=stage.id if stage else "",
                stageName=stage.name if stage else "",
                candidate=_serialize_candidate(candidate),
                jobTitle=application.jobPosting.title if application.jobPosting else "",
                jobPostingId=application.jobPosting.id if application.jobPosting else "",
                jobSlug=application.jobPosting.slug if application.jobPosting else None,
                scheduledStartAt=event.scheduledStartAt,
                scheduledEndAt=event.scheduledEndAt,
                status=display_status,
                role=participant.role or "INTERVIEWER",
                isBackup=is_backup,
                meetingUrl=event.meetingUrl,
                stageDueDate=stage.dueDate if stage else None,
                evaluationCategories=[
                    _serialize_category(category)
                    for category in sorted(stage.evaluationCategories or [], key=lambda item: item.order)
                ] if stage else [],
            )
        )
    return MyInterviewListResponse(items=items)


async def create_reassignment_request(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    member_id: str,
    body: ReassignmentRequestCreate,
) -> None:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_with_participants(organization_id, body.eventId)
    if event is None:
        raise HTTPException(status_code=404, detail="Interview event not found")

    # Find the requesting member's participant record
    participant = None
    for p in (event.participants or []):
        if p.memberId == member_id:
            participant = p
            break
    if participant is None:
        raise HTTPException(status_code=400, detail="You are not assigned to this interview")

    # Email HR/admin — for now just email the actor who created the event if available
    hr_email = None
    if event.createdBy is not None and event.createdBy.user is not None:
        hr_email = event.createdBy.user.email

    email_service = ResendEmailService()
    candidate_name = _candidate_display_name(event.application)
    interviewer_name = participant.member.user.name if participant.member and participant.member.user else ""
    interviewer_email = participant.member.user.email if participant.member and participant.member.user else ""

    if hr_email:
        await email_service.send_reassignment_notification_to_hr(
            to_email=hr_email,
            interviewer_name=interviewer_name,
            interviewer_email=interviewer_email,
            candidate_name=candidate_name,
            stage_name=event.stage.name if event.stage else "",
            organization_name=organization_name,
            reason=body.reason,
        )
    await db.commit()


def _candidate_display_name(application: CandidateApplication) -> str:
    return _candidate_name(application) or application.candidate.email


def _meeting_time_text(starts_at: datetime) -> str:
    value = starts_at
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    ist = value.astimezone(UTC) + timedelta(hours=5, minutes=30)
    return ist.strftime("%d %b %Y, %I:%M %p IST")


async def create_interview_meeting(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    actor_user_id: str,
    application_id: str,
    body: InterviewMeetingCreateRequest,
    access_scope: str | None = None,
) -> InterviewMeetingRead:
    repository = CandidatePipelineRepository(db)
    application = await repository.get_application(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    stage = application.pipelineStage
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if not stage.meetingEnabled:
        raise HTTPException(status_code=400, detail="Meetings are not enabled for this stage")

    latest_event = await repository.get_latest_stage_event(
        organization_id,
        application.id,
        stage.id,
    )
    if access_scope == "self":
        if latest_event is None:
            raise HTTPException(status_code=403, detail="you dont have permission")
        _ensure_self_interview_access(latest_event, actor_member_id, access_scope)

    starts_at = body.scheduledStartAt if body.mode == "SCHEDULE" else datetime.now(UTC)
    if starts_at is None:
        raise HTTPException(status_code=400, detail="Start time is required")
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    starts_at = starts_at.astimezone(UTC)
    ends_at = starts_at + timedelta(minutes=body.durationMinutes)

    candidate_name = _candidate_display_name(application)
    title = (body.title or f"{stage.name} interview - {candidate_name}").strip()
    description_parts = [
        f"Interview for {application.jobPosting.title}",
        f"Candidate: {candidate_name}",
        f"Stage: {stage.name}",
    ]
    if body.notes:
        description_parts.append(f"Notes: {body.notes.strip()}")

    if body.mode == "SCHEDULE":
        calendar_service = GoogleCalendarService(db)
        meeting = await calendar_service.create_meet_event(
            user_id=actor_user_id,
            summary=title,
            description="\n".join(description_parts),
            starts_at=starts_at,
            ends_at=ends_at,
        )

        await ResendEmailService().send_interview_invite(
            to_email=application.candidate.email,
            candidate_name=candidate_name,
            job_title=application.jobPosting.title,
            stage_name=stage.name,
            starts_at_text=_meeting_time_text(meeting.starts_at),
            meeting_url=meeting.meeting_url,
        )

        created_new_event = latest_event is not None and latest_event.status == EventStatus.COMPLETED
        event = (None if created_new_event else latest_event) or StageEvent(
            organizationId=organization_id,
            applicationId=application.id,
            stageId=stage.id,
            createdByMemberId=actor_member_id,
            title=title,
            description="\n".join(description_parts),
            interviewType=InterviewType.OTHER,
            status=EventStatus.SCHEDULED,
        )
        event.title = title
        event.description = "\n".join(description_parts)
        event.status = EventStatus.SCHEDULED
        event.scheduledStartAt = meeting.starts_at
        event.scheduledEndAt = meeting.ends_at
        event.notes = body.notes
        event.meetingUrl = meeting.meeting_url
        event.googleCalendarEventId = meeting.event_id
        event.googleCalendarEventUrl = meeting.html_link
        event.emailSentAt = datetime.now(UTC)
        await repository.add_stage_event(event)
        if access_scope == "self" and created_new_event:
            await db.flush()
            db.add(
                StageEventParticipant(
                    eventId=event.id,
                    memberId=actor_member_id,
                    role="INTERVIEWER",
                    approvalStatus="SCHEDULED",
                    approvedAt=datetime.now(UTC),
                    scheduledTime=meeting.starts_at,
                )
            )
        await db.commit()
        return _serialize_interview_meeting(event)

    if latest_event is not None and latest_event.meetingUrl and latest_event.status != EventStatus.COMPLETED:
        return _serialize_interview_meeting(latest_event)

    calendar_service = GoogleCalendarService(db)
    meeting = await calendar_service.create_meet_event(
        user_id=actor_user_id,
        summary=title,
        description="\n".join(description_parts),
        starts_at=starts_at,
        ends_at=ends_at,
    )

    await ResendEmailService().send_interview_invite(
        to_email=application.candidate.email,
        candidate_name=candidate_name,
        job_title=application.jobPosting.title,
        stage_name=stage.name,
        starts_at_text=_meeting_time_text(meeting.starts_at),
        meeting_url=meeting.meeting_url,
    )

    created_new_event = latest_event is not None and latest_event.status == EventStatus.COMPLETED
    event = (None if created_new_event else latest_event) or StageEvent(
        organizationId=organization_id,
        applicationId=application.id,
        stageId=stage.id,
        createdByMemberId=actor_member_id,
        title=title,
        description="\n".join(description_parts),
        interviewType=InterviewType.OTHER,
        status=EventStatus.SCHEDULED,
    )
    event.title = title
    event.description = "\n".join(description_parts)
    event.status = EventStatus.SCHEDULED
    event.scheduledStartAt = meeting.starts_at
    event.scheduledEndAt = meeting.ends_at
    event.meetingUrl = meeting.meeting_url
    event.googleCalendarEventId = meeting.event_id
    event.googleCalendarEventUrl = meeting.html_link
    event.notes = body.notes
    event.emailSentAt = datetime.now(UTC)
    await repository.add_stage_event(event)
    if access_scope == "self" and created_new_event:
        await db.flush()
        db.add(
            StageEventParticipant(
                eventId=event.id,
                memberId=actor_member_id,
                role="INTERVIEWER",
                approvalStatus="SCHEDULED",
                approvedAt=datetime.now(UTC),
                scheduledTime=meeting.starts_at,
            )
        )
    await db.commit()
    return _serialize_interview_meeting(event)


async def update_interview_meeting(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    actor_user_id: str,
    application_id: str,
    event_id: str,
    body: InterviewMeetingUpdateRequest,
    access_scope: str | None = None,
) -> InterviewMeetingRead:
    repository = CandidatePipelineRepository(db)
    application = await repository.get_application(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    stage = application.pipelineStage
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if not stage.meetingEnabled:
        raise HTTPException(status_code=400, detail="Meetings are not enabled for this stage")

    latest_event = await repository.get_latest_stage_event(
        organization_id,
        application.id,
        stage.id,
    )
    if latest_event is None or latest_event.id != event_id:
        raise HTTPException(status_code=404, detail="Interview meeting not found")
    _ensure_self_interview_access(latest_event, actor_member_id, access_scope)
    if latest_event.status != EventStatus.SCHEDULED:
        raise HTTPException(status_code=400, detail="Only scheduled interviews can be rescheduled")

    starts_at = body.scheduledStartAt
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=UTC)
    starts_at = starts_at.astimezone(UTC)
    ends_at = starts_at + timedelta(minutes=body.durationMinutes)

    candidate_name = _candidate_display_name(application)
    title = (body.title or latest_event.title or f"{stage.name} interview - {candidate_name}").strip()
    description_parts = [
        f"Interview for {application.jobPosting.title}",
        f"Candidate: {candidate_name}",
        f"Stage: {stage.name}",
    ]
    if body.notes:
        description_parts.append(f"Notes: {body.notes.strip()}")

    calendar_service = GoogleCalendarService(db)
    meeting = await calendar_service.update_meet_event(
        user_id=actor_user_id,
        event_id=latest_event.googleCalendarEventId or event_id,
        summary=title,
        description="\n".join(description_parts),
        starts_at=starts_at,
        ends_at=ends_at,
    )

    await ResendEmailService().send_interview_rescheduled(
        to_email=application.candidate.email,
        candidate_name=candidate_name,
        job_title=application.jobPosting.title,
        stage_name=stage.name,
        starts_at_text=_meeting_time_text(meeting.starts_at),
        meeting_url=meeting.meeting_url,
    )

    latest_event.title = title
    latest_event.description = "\n".join(description_parts)
    latest_event.status = EventStatus.SCHEDULED
    latest_event.scheduledStartAt = meeting.starts_at
    latest_event.scheduledEndAt = meeting.ends_at
    latest_event.meetingUrl = meeting.meeting_url
    latest_event.googleCalendarEventId = meeting.event_id
    latest_event.googleCalendarEventUrl = meeting.html_link
    latest_event.notes = body.notes
    latest_event.emailSentAt = datetime.now(UTC)
    await repository.add_stage_event(latest_event)
    await db.commit()
    return _serialize_interview_meeting(latest_event)


async def start_interview_meeting(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    actor_user_id: str,
    application_id: str,
    event_id: str,
    access_scope: str | None = None,
) -> InterviewMeetingRead:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event(organization_id, application_id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Interview meeting not found")
    _ensure_self_interview_access(event, actor_member_id, access_scope)
    if event.status != EventStatus.SCHEDULED:
        raise HTTPException(status_code=400, detail="Only scheduled interviews can be started")

    event.status = EventStatus.ONGOING
    await repository.add_stage_event(event)
    await db.commit()

    application = event.application
    stage = event.stage
    candidate_name = _candidate_display_name(application) if application else "Candidate"
    stage_or_job_title = stage.name if stage else "Interview"

    if application and event.meetingUrl and application.candidate:
        await ResendEmailService().send_interview_meeting_ready(
            to_email=application.candidate.email,
            candidate_name=candidate_name,
            job_title=stage_or_job_title,
            meeting_url=event.meetingUrl,
        )

    return _serialize_interview_meeting(event)


async def complete_interview_meeting(
    db: AsyncSession,
    organization_id: str,
    application_id: str,
    event_id: str,
    actor_member_id: str,
    actor_user_id: str,
    body: InterviewMeetingCompleteRequest,
    access_scope: str | None = None,
) -> InterviewMeetingRead:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event(organization_id, application_id, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Interview meeting not found")
    _ensure_self_interview_access(event, actor_member_id, access_scope)
    if event.scheduledStartAt is None or event.scheduledEndAt is None:
        raise HTTPException(status_code=400, detail="Interview meeting is missing schedule metadata")

    stage = event.stage
    categories = _ordered_stage_categories(stage) if stage is not None else []
    values_by_category = {item.categoryId: item.value for item in body.values}

    feedback = next(
        (
            item
            for item in event.__dict__.get("feedbacks", [])
            if item.memberId == actor_member_id
        ),
        None,
    )
    existing_values: dict[str, InterviewFeedbackValue] = {}
    if feedback is None:
        feedback = InterviewFeedback(
            organizationId=organization_id,
            eventId=event.id,
            memberId=actor_member_id,
        )
        db.add(feedback)
        await db.flush()
    else:
        existing_values = {
            item.categoryId: item
            for item in feedback.__dict__.get("values", [])
        }

    feedback.notes = body.notes
    numeric_scores: list[float] = []
    for category in categories:
        raw_value = values_by_category.get(category.id)
        value = existing_values.get(category.id)
        if value is None:
            value = InterviewFeedbackValue(
                feedbackId=feedback.id,
                categoryId=category.id,
            )
            db.add(value)
        value.numericValue = None
        value.textValue = None
        value.booleanValue = None
        if category.valueType == "CHECKBOX":
            value.booleanValue = bool(raw_value)
        elif category.valueType == "TEXT":
            value.textValue = "" if raw_value is None else str(raw_value)
        else:
            try:
                numeric_value = float(raw_value) if raw_value not in (None, "") else None
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Invalid numeric score for {category.name}") from None
            value.numericValue = numeric_value
            if numeric_value is not None:
                numeric_scores.append(numeric_value)
    feedback.score = round(sum(numeric_scores)) if numeric_scores else None

    event.status = EventStatus.COMPLETED
    event.completedByMemberId = actor_member_id
    now = datetime.now(UTC)
    event.scheduledEndAt = now
    db.add(event)
    await db.flush()

    if stage is not None and stage.evaluationWorkspace is not None:
        await _write_feedback_to_stage_sheet(
            db,
            actor_user_id,
            stage,
            event.application,
            body.values,
            body.notes,
        )

    await db.commit()
    return _serialize_interview_meeting(event)


def _candidate_name(application: CandidateApplication) -> str:
    return f"{application.candidate.firstName} {application.candidate.lastName}".strip()


def _stage_tab_title(stage: PipelineStage) -> str:
    return f"{stage.order}. {stage.name}"


def _ordered_stage_categories(stage: PipelineStage) -> list[StageEvaluationCategory]:
    return sorted(
        stage.__dict__.get("evaluationCategories", []),
        key=lambda item: item.order,
    )


def _stage_headers(stage: PipelineStage) -> list[str]:
    categories = _ordered_stage_categories(stage)
    headers = ["Candidate", "Email"]
    headers.extend(category.name for category in categories)
    if stage.evaluationIncludeTotal:
        headers.append("Total")
    headers.append("Notes")
    return headers


def _column_letter(index: int) -> str:
    value = index + 1
    letters = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _stage_candidate_row(
    stage: PipelineStage,
    application: CandidateApplication,
    row_number: int | None = None,
) -> list[str]:
    categories = _ordered_stage_categories(stage)
    row = [
        _candidate_name(application),
        application.candidate.email,
    ]
    row.extend("" for _ in categories)
    if stage.evaluationIncludeTotal:
        if categories and row_number is not None:
            start = _column_letter(2)
            end = _column_letter(1 + len(categories))
            row.append(f"=SUM({start}{row_number}:{end}{row_number})")
        else:
            row.append("")
    row.append("")
    return row


def _feedback_sheet_value(category: StageEvaluationCategory, raw_value: object) -> str:
    if raw_value is None:
        return ""
    if category.valueType == "CHECKBOX":
        return "TRUE" if bool(raw_value) else "FALSE"
    return str(raw_value)


async def _write_feedback_to_stage_sheet(
    db: AsyncSession,
    user_id: str,
    stage: PipelineStage,
    application: CandidateApplication,
    feedback_values: list[object],
    notes: str | None,
) -> None:
    workspace = stage.evaluationWorkspace
    if workspace is None:
        return

    values_by_category = {
        item.categoryId: item.value
        for item in feedback_values
        if hasattr(item, "categoryId")
    }
    categories = _ordered_stage_categories(stage)
    row_values = [_feedback_sheet_value(category, values_by_category.get(category.id)) for category in categories]
    if stage.evaluationIncludeTotal:
        numeric_values = []
        for category in categories:
            if category.valueType != "NUMERIC":
                continue
            raw_value = values_by_category.get(category.id)
            try:
                if raw_value not in (None, ""):
                    numeric_values.append(float(raw_value))
            except (TypeError, ValueError):
                pass
        row_values.append(str(sum(numeric_values)) if numeric_values else "")
    row_values.append(notes or "")

    sheets_service = GoogleSheetsService(db)
    sheet_values = await sheets_service.get_values(
        user_id,
        workspace.googleSpreadsheetId,
        workspace.googleSheetTitle,
    )
    candidate_email = application.candidate.email.strip().lower()
    target_row = next(
        (
            index
            for index, row in enumerate(sheet_values, start=1)
            if index > 1 and len(row) >= 2 and row[1].strip().lower() == candidate_email
        ),
        None,
    )
    if target_row is None:
        target_row = len(sheet_values) + 1
        await sheets_service.append_values(
            user_id,
            workspace.googleSpreadsheetId,
            workspace.googleSheetTitle,
            [_stage_candidate_row(stage, application, row_number=target_row)],
        )

    await sheets_service.write_values(
        user_id,
        workspace.googleSpreadsheetId,
        [
            SheetValueBlock(
                sheet_title=workspace.googleSheetTitle,
                values=[row_values],
                start_cell=f"C{target_row}",
            )
        ],
    )


def _stage_sheet_values(stage: PipelineStage) -> list[list[str]]:
    applications = sorted(
        stage.__dict__.get("applications", []),
        key=lambda application: application.appliedAt,
    )
    return [
        _stage_headers(stage),
        *[
            _stage_candidate_row(stage, application, row_number=index)
            for index, application in enumerate(applications, start=2)
        ],
    ]


def _existing_candidate_emails(values: list[list[str]]) -> set[str]:
    return {
        row[1].strip().lower()
        for row in values[1:]
        if len(row) >= 2 and row[1]
    }


def _sheet_formula_quote(title: str) -> str:
    return sanitize_sheet_title(title).replace("'", "''")


def _analysis_formula(
    sheet_title: str,
    source_column_index: int,
    target_row_number: int,
) -> str:
    source_column = _column_letter(source_column_index)
    return (
        f"=IFERROR(INDEX(FILTER('{_sheet_formula_quote(sheet_title)}'!"
        f"{source_column}:{source_column},"
        f"'{_sheet_formula_quote(sheet_title)}'!$B:$B=$B{target_row_number}),1),\"\")"
    )


def _analysis_sheet_values(stages: list[PipelineStage]) -> AnalysisSheetData:
    evaluation_stages = [stage for stage in stages if stage.evaluationIncludeAnalysis]
    if not evaluation_stages:
        return AnalysisSheetData(values=[], merge_ranges=[])

    first_header = ["Candidate", "Email"]
    second_header = ["", ""]
    seen_applications: dict[str, CandidateApplication] = {}
    merge_ranges: list[AnalysisMergeRange] = []
    stage_columns: list[tuple[PipelineStage, list[str]]] = []

    for stage in evaluation_stages:
        categories = _ordered_stage_categories(stage)
        stage_headers = [category.name for category in categories]
        if stage.evaluationIncludeTotal:
            stage_headers.append("Total")
        if not stage_headers:
            stage_headers = ["Evaluation"]
        stage_start = len(first_header)
        first_header.extend([stage.name, *["" for _ in stage_headers[1:]]])
        second_header.extend(stage_headers)
        merge_ranges.append(
            AnalysisMergeRange(
                start_column_index=stage_start,
                end_column_index=stage_start + len(stage_headers),
            )
        )
        stage_columns.append((stage, stage_headers))
        for application in stage.__dict__.get("applications", []):
            seen_applications[application.candidate.email.lower()] = application

    rows = []
    for row_number, application in enumerate(
        sorted(seen_applications.values(), key=lambda item: _candidate_name(item).lower()),
        start=3,
    ):
        row = [
            _candidate_name(application),
            application.candidate.email,
        ]
        for stage, stage_headers in stage_columns:
            stage_sheet_title = (
                stage.evaluationWorkspace.googleSheetTitle
                if stage.evaluationWorkspace
                else _stage_tab_title(stage)
            )
            for offset, _header in enumerate(stage_headers):
                row.append(_analysis_formula(stage_sheet_title, 2 + offset, row_number))
        rows.append(row)
    return AnalysisSheetData(values=[first_header, second_header, *rows], merge_ranges=merge_ranges)


async def _append_missing_stage_candidates(
    sheets_service: GoogleSheetsService,
    user_id: str,
    spreadsheet_id: str,
    stage: PipelineStage,
    sheet_title: str,
) -> None:
    values = await sheets_service.get_values(user_id, spreadsheet_id, sheet_title)
    existing_emails = _existing_candidate_emails(values)
    rows = [
        _stage_candidate_row(stage, application, row_number=index)
        for index, application in enumerate(
            [
                item
                for item in sorted(stage.__dict__.get("applications", []), key=lambda item: item.appliedAt)
                if item.candidate.email.lower() not in existing_emails
            ],
            start=len(values) + 1,
        )
    ]
    await sheets_service.append_values(user_id, spreadsheet_id, sheet_title, rows)


async def _format_stage_evaluation_sheet(
    sheets_service: GoogleSheetsService,
    user_id: str,
    spreadsheet_id: str,
    stage: PipelineStage,
    sheet_id: int | None,
) -> None:
    if sheet_id is None:
        return
    await sheets_service.format_stage_sheet(
        user_id,
        spreadsheet_id,
        sheet_id,
        stage.evaluationType,
        len(_ordered_stage_categories(stage)),
        max(len(stage.__dict__.get("applications", [])) + 1, 2),
    )


async def _remove_legacy_application_id_column(
    sheets_service: GoogleSheetsService,
    user_id: str,
    spreadsheet_id: str,
    sheet_title: str,
    sheet_id: int | None,
) -> None:
    if sheet_id is None:
        return
    values = await sheets_service.get_values(user_id, spreadsheet_id, sheet_title, "A1:Z1")
    if values and len(values[0]) >= 3 and values[0][2].strip().lower() == "application id":
        await sheets_service.delete_column(user_id, spreadsheet_id, sheet_id, 2)


async def _update_analysis_sheet(
    db: AsyncSession,
    repository: CandidatePipelineRepository,
    sheets_service: GoogleSheetsService,
    organization_id: str,
    user_id: str,
    job_posting_id: str,
    spreadsheet_id: str,
) -> None:
    stages = await repository.list_evaluation_stages_for_job(organization_id, job_posting_id)
    data = _analysis_sheet_values(stages)
    if not data.values:
        return

    analysis_title = "Overall Analysis"
    analysis_sheet_id = await sheets_service.get_sheet_id(user_id, spreadsheet_id, analysis_title)
    if analysis_sheet_id is None:
        try:
            tab = await sheets_service.create_sheet_tab(user_id, spreadsheet_id, analysis_title)
            analysis_sheet_id = tab.sheet_id
        except HTTPException as error:
            if "already exists" not in str(error.detail).lower():
                raise
            analysis_sheet_id = await sheets_service.get_sheet_id(user_id, spreadsheet_id, analysis_title)

    if analysis_sheet_id is not None:
        await sheets_service.unmerge_header_row(
            user_id,
            spreadsheet_id,
            analysis_sheet_id,
            len(data.values[0]),
        )
    await sheets_service.clear_values(user_id, spreadsheet_id, analysis_title)
    await sheets_service.write_values(
        user_id,
        spreadsheet_id,
        [SheetValueBlock(sheet_title=analysis_title, values=data.values)],
    )
    if analysis_sheet_id is not None:
        await sheets_service.format_analysis_sheet(
            user_id,
            spreadsheet_id,
            analysis_sheet_id,
            data.merge_ranges,
            len(data.values[0]),
        )


async def _ensure_stage_evaluation_workspace(
    db: AsyncSession,
    repository: CandidatePipelineRepository,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    actor_user_id: str,
    stage: PipelineStage,
) -> StageEvaluationWorkspace:
    existing = stage.__dict__.get("evaluationWorkspace") or await repository.get_evaluation_workspace(
        organization_id,
        stage.id,
    )
    sheets_service = GoogleSheetsService(db)

    if existing is not None:
        desired_title = _stage_tab_title(stage)
        if existing.googleSheetId is not None and existing.googleSheetTitle != desired_title:
            try:
                existing.googleSheetTitle = await sheets_service.rename_sheet_tab(
                    actor_user_id,
                    existing.googleSpreadsheetId,
                    existing.googleSheetId,
                    desired_title,
                )
                db.add(existing)
                await db.flush()
            except HTTPException as error:
                if "already exists" not in str(error.detail).lower():
                    raise
        await _remove_legacy_application_id_column(
            sheets_service,
            actor_user_id,
            existing.googleSpreadsheetId,
            existing.googleSheetTitle,
            existing.googleSheetId,
        )
        await sheets_service.clear_values(
            actor_user_id,
            existing.googleSpreadsheetId,
            existing.googleSheetTitle,
            "A1:ZZ1",
        )
        await sheets_service.write_values(
            actor_user_id,
            existing.googleSpreadsheetId,
            [SheetValueBlock(sheet_title=existing.googleSheetTitle, values=[_stage_headers(stage)])],
        )
        await _append_missing_stage_candidates(
            sheets_service,
            actor_user_id,
            existing.googleSpreadsheetId,
            stage,
            existing.googleSheetTitle,
        )
        await _format_stage_evaluation_sheet(
            sheets_service,
            actor_user_id,
            existing.googleSpreadsheetId,
            stage,
            existing.googleSheetId,
        )
        await _update_analysis_sheet(
            db,
            repository,
            sheets_service,
            organization_id,
            actor_user_id,
            stage.jobPostingId,
            existing.googleSpreadsheetId,
        )
        return existing

    job_workspace = await repository.get_any_evaluation_workspace_for_job(
        organization_id,
        stage.jobPostingId,
    )
    desired_title = _stage_tab_title(stage)

    if job_workspace is None:
        spreadsheet = await sheets_service.create_evaluation_spreadsheet(
            user_id=actor_user_id,
            title=f"{organization_name} - {stage.jobPosting.title}",
            first_tab_title=desired_title,
            value_blocks=[
                SheetValueBlock(
                    sheet_title=desired_title,
                    values=_stage_sheet_values(stage),
                )
            ],
        )
        workspace = StageEvaluationWorkspace(
            organizationId=organization_id,
            stageId=stage.id,
            googleSpreadsheetId=spreadsheet.spreadsheet_id,
            googleSpreadsheetUrl=spreadsheet.spreadsheet_url,
            googleSheetId=spreadsheet.sheet_id,
            googleSheetTitle=spreadsheet.sheet_title,
            createdByMemberId=actor_member_id,
        )
        await _format_stage_evaluation_sheet(
            sheets_service,
            actor_user_id,
            spreadsheet.spreadsheet_id,
            stage,
            spreadsheet.sheet_id,
        )
    else:
        stages = await repository.list_evaluation_stages_for_job(organization_id, stage.jobPostingId)
        existing_titles = [
            item.evaluationWorkspace.googleSheetTitle
            for item in stages
            if item.evaluationWorkspace is not None
        ]
        tab_title = make_unique_sheet_titles([*existing_titles, desired_title])[-1]
        tab = await sheets_service.create_sheet_tab(
            actor_user_id,
            job_workspace.googleSpreadsheetId,
            tab_title,
        )
        await sheets_service.write_values(
            actor_user_id,
            job_workspace.googleSpreadsheetId,
            [
                SheetValueBlock(
                    sheet_title=tab.sheet_title,
                    values=_stage_sheet_values(stage),
                )
            ],
        )
        workspace = StageEvaluationWorkspace(
            organizationId=organization_id,
            stageId=stage.id,
            googleSpreadsheetId=job_workspace.googleSpreadsheetId,
            googleSpreadsheetUrl=job_workspace.googleSpreadsheetUrl,
            googleSheetId=tab.sheet_id,
            googleSheetTitle=tab.sheet_title,
            createdByMemberId=actor_member_id,
        )
        await _format_stage_evaluation_sheet(
            sheets_service,
            actor_user_id,
            job_workspace.googleSpreadsheetId,
            stage,
            tab.sheet_id,
        )

    await repository.add_evaluation_workspace(workspace)
    await db.flush()
    await _update_analysis_sheet(
        db,
        repository,
        sheets_service,
        organization_id,
        actor_user_id,
        stage.jobPostingId,
        workspace.googleSpreadsheetId,
    )
    return workspace


async def _sync_stage_evaluation_workspace_if_needed(
    db: AsyncSession,
    repository: CandidatePipelineRepository,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    actor_user_id: str,
    stage: PipelineStage,
) -> None:
    if not stage.evaluationEnabled or not stage.sheetEnabled:
        return
    await _ensure_stage_evaluation_workspace(
        db,
        repository,
        organization_id,
        organization_name,
        actor_member_id,
        actor_user_id,
        stage,
    )


async def get_evaluation_workspace(
    db: AsyncSession,
    organization_id: str,
    stage_id: str,
) -> StageEvaluationWorkspaceRead:
    repository = CandidatePipelineRepository(db)
    workspace = await repository.get_evaluation_workspace(organization_id, stage_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Evaluation workspace not found")
    serialized = _serialize_workspace(workspace)
    if serialized is None:
        raise HTTPException(status_code=404, detail="Evaluation workspace not found")
    return serialized


async def generate_evaluation_workspace(
    db: AsyncSession,
    organization_id: str,
    organization_name: str,
    actor_member_id: str,
    actor_user_id: str,
    stage_id: str,
) -> StageEvaluationWorkspaceRead:
    repository = CandidatePipelineRepository(db)
    stage = await repository.get_stage(organization_id, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    if not stage.evaluationEnabled:
        raise HTTPException(status_code=400, detail="Evaluation is not enabled for this stage")

    workspace = await _ensure_stage_evaluation_workspace(
        db,
        repository,
        organization_id,
        organization_name,
        actor_member_id,
        actor_user_id,
        stage,
    )
    await db.commit()
    await db.refresh(workspace)
    serialized = _serialize_workspace(workspace)
    if serialized is None:
        raise HTTPException(status_code=500, detail="Evaluation workspace was not created")
    return serialized
