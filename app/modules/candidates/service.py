from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.email.resend_service import ResendEmailService
from app.integrations.google.calendar_service import GoogleCalendarService
from app.models.member import Member
from app.models.recruitment import (
    ApplicationStageHistory,
    Candidate,
    CandidateApplication,
    CandidateApplicationNote,
    EventStatus,
    InterviewFeedback,
    InterviewRejectionRecord,
    InterviewType,
    PipelineStage,
    StageEvent,
    StageEventParticipant,
    StageEventProposedSlot,
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
    FeedbackInfoResponse,
    FeedbackSubmitRequest,
    FeedbackSubmitResponse,
    InterviewAcceptRequest,
    InterviewAcceptResponse,
    InterviewerSearchResponse,
    InterviewFeedbackRead,
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
    PublicProposedSlotRead,
    ReassignmentRequestCreate,
    ReshuffleRequest,
    ReshuffleResponse,
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


def _is_protected_stage(stage: PipelineStage) -> bool:
    return stage.name.strip().lower() == "applied" and stage.order == 1


def _single_stage_type_error(stage_type: StageType) -> str | None:
    return {
        StageType.OFFER: "This job already has an offer stage.",
        StageType.HIRED: "This job already has an accepted stage.",
        StageType.REJECTED: "This job already has a rejected stage.",
        StageType.ONBOARDING: "This job already has an onboard stage.",
    }.get(stage_type)


async def _assert_single_stage_type(
    db: AsyncSession,
    organization_id: str,
    job_posting_id: str,
    stage_type: StageType,
    *,
    excluded_stage_id: str | None = None,
) -> None:
    message = _single_stage_type_error(stage_type)
    if message is None:
        return
    query = select(PipelineStage.id).where(
        PipelineStage.organizationId == organization_id,
        PipelineStage.jobPostingId == job_posting_id,
        PipelineStage.stageType == stage_type,
    )
    if excluded_stage_id is not None:
        query = query.where(PipelineStage.id != excluded_stage_id)
    result = await db.execute(query.limit(1))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=message)


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
    ai_analysis = application.resumeAnalysis
    return PipelineApplicationRead(
        id=application.id,
        jobPostingId=application.jobPostingId,
        pipelineStageId=application.pipelineStageId,
        currentStage=stage.name,
        candidate=_serialize_candidate(application.candidate),
        source=application.source,
        appliedDate=application.appliedAt,
        lastMovedAt=_last_moved_at(application),
        status=_application_status(application, stage),
        resumeUrl=application.candidate.resumeUrl,
        aiScore=ai_analysis.compositeScore if ai_analysis is not None else None,
        aiAnalysisStatus=ai_analysis.status if ai_analysis is not None else None,
        aiEvaluationStatus=ai_analysis.evaluationStatus if ai_analysis is not None else None,
        isFlaggedForCheating=(
            bool(ai_analysis.isFlaggedForCheating) if ai_analysis is not None else False
        ),
        aiFailedKnockouts=(
            list(ai_analysis.failedKnockouts or []) if ai_analysis is not None else []
        ),
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
        dueDate=stage.dueDate,
        completedAt=stage.completedAt,
        extendToNextWorkingDay=False,
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


def _serialize_feedback(feedback: InterviewFeedback) -> InterviewFeedbackRead:
    name, _email = _member_display(feedback.member)
    return InterviewFeedbackRead(
        id=feedback.id,
        memberId=feedback.memberId,
        memberName=name or "Unknown",
        outcome=feedback.outcome.value if hasattr(feedback.outcome, "value") else str(feedback.outcome),
        notes=feedback.notes,
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
    if name := getattr(user, "name", None):
        pass
    elif email:
        local_part = email.split("@")[0]
        name = local_part.replace(".", " ").replace("_", " ").replace("-", " ").title().strip()
    else:
        name = "Interviewer"
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
        if (participant.role == "INTERVIEWER" or participant.role is None) and participant.approvalStatus != "REJECTED":
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
        appliedAt=application.appliedAt,
        currentAssignment=_serialize_workspace_assignment(
            _latest_assignment_event(application, stage.id)
        ),
    )


def _serialize_stage_workspace(
    stage: PipelineStage,
    team_members: list[Member] | None = None,
    assignment_team_id: str | None = None,
) -> StageWorkspaceRead:
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
        teamMembers=[_serialize_interviewer(m) for m in (team_members or [])],
        assignmentTeamId=assignment_team_id,
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


async def _apply_stage_config(
    db: AsyncSession,
    organization_id: str,
    stage: PipelineStage,
    body: PipelineStageCreateRequest | PipelineStageUpdateRequest,
) -> None:
    next_stage_type = stage.stageType
    if getattr(body, "stageType", None) is not None:
        next_stage_type = StageType(str(body.stageType).strip().upper())
    await _assert_single_stage_type(
        db,
        organization_id,
        stage.jobPostingId,
        next_stage_type,
        excluded_stage_id=stage.id,
    )
    stage.stageType = next_stage_type
    stage.meetingEnabled = next_stage_type == StageType.INTERVIEW
    stage.offerLetterEnabled = next_stage_type in {StageType.OFFER, StageType.ONBOARDING}
    stage.isFinal = next_stage_type in {StageType.HIRED, StageType.REJECTED, StageType.ONBOARDING}

    if isinstance(body, PipelineStageUpdateRequest) and body.dueDateEnabled is False:
        stage.dueDate = None
    elif body.dueDate is not None:
        stage.dueDate = body.dueDate

    stage.extendToNextWorkingDay = False


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
    access_scope: str | None = None,
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
    assignment_team_id = None
    team_members = []
    job_posting_id = stage.jobPosting.id if stage.jobPosting else None
    if job_posting_id:
        primary_team = await repository.get_primary_hiring_team(
            organization_id, job_posting_id, stage.id
        )
        if primary_team:
            assignment_team_id = primary_team.id
            team_members = [m.member for m in primary_team.members]
    return _serialize_stage_workspace(stage, team_members=team_members, assignment_team_id=assignment_team_id)


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
    assignment_team_id = None
    team_members = []
    primary_team = await repository.get_primary_hiring_team(
        organization_id, posting.id, stage.id
    )
    if primary_team:
        assignment_team_id = primary_team.id
        team_members = [m.member for m in primary_team.members]
    return _serialize_stage_workspace(stage, team_members=team_members, assignment_team_id=assignment_team_id)


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
        for member_id in [assignment.interviewerMemberId]
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
            )
        )

    warnings = await _build_assignment_warnings(repository, organization_id, assignments)
    if warnings and not body.ignoreWarnings:
        return TeamDistributionResponse(assignedCount=0, warnings=warnings)

    members = await repository.get_members_by_ids(
        organization_id,
        list(dict.fromkeys(team_member_ids)),
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
        # Auto reshuffle: find team member with fewest active interviews who hasn't rejected
        current_primary = None
        for p in (event.participants or []):
            if p.role == "INTERVIEWER" or p.role is None:
                current_primary = p
                break

        if current_primary is None:
            raise HTTPException(status_code=400, detail="No primary interviewer to reshuffle")

        rejected_member_ids = await repository.list_rejected_member_ids_for_event(organization_id, event.id)
        rejected_member_ids.add(current_primary.memberId)

        existing_member_ids = {p.memberId for p in (event.participants or [])}

        team_member_ids = await repository.get_primary_hiring_team_member_ids(
            organization_id,
            event.stage.jobPostingId,
            event.stage.id,
        )
        available_member_ids = [
            mid for mid in team_member_ids
            if mid not in rejected_member_ids and mid not in existing_member_ids
        ]

        if not available_member_ids:
            raise HTTPException(status_code=400, detail="No team member available for auto-reshuffle")

        active_counts = await repository.count_active_interviews_for_members(
            organization_id,
            available_member_ids,
        )
        new_member_id = min(
            available_member_ids,
            key=lambda mid: (active_counts.get(mid, 0), mid),
        )

    # Swap primary: demote old, promote new
    for p in (event.participants or []):
        if p.memberId == new_member_id:
            p.role = "INTERVIEWER"
            p.isBackup = False
            p.approvalStatus = "PENDING_ACCEPTANCE"
        elif p.role == "INTERVIEWER" or p.role is None:
            p.approvalStatus = "REJECTED"

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
    is_reschedule = (
        event.status in {EventStatus.SCHEDULED, EventStatus.ONGOING, EventStatus.COMPLETED}
        or participant.approvalStatus == "SCHEDULED"
    )

    normalized_slots: list[tuple[datetime, datetime]] = []
    for slot in body.proposedSlots:
        starts_at = slot.startTime
        ends_at = slot.endTime
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=UTC)
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=UTC)
        starts_at = starts_at.astimezone(UTC)
        ends_at = ends_at.astimezone(UTC)

        if starts_at < now:
            raise HTTPException(status_code=400, detail="Interview cannot be scheduled in the past")
        if ends_at <= starts_at:
            raise HTTPException(status_code=400, detail="End time must be after start time")
        if event.stage is not None and event.stage.dueDate is not None:
            due_date = event.stage.dueDate
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=UTC)
            if starts_at > due_date.astimezone(UTC):
                raise HTTPException(status_code=400, detail="Interview cannot be scheduled after the stage due date")

        normalized_slots.append((starts_at, ends_at))

    participant.approvedAt = now
    participant.approvalStatus = "ACCEPTED"
    participant.scheduledTime = None
    db.add(participant)

    event.status = EventStatus.SCHEDULED
    event.scheduledStartAt = None
    event.scheduledEndAt = None
    event.meetingUrl = None
    event.googleCalendarEventId = None
    event.googleCalendarEventUrl = None
    event.completedByMemberId = None
    event.proposedSlots.clear()

    for starts_at, ends_at in normalized_slots:
        event.proposedSlots.append(
            StageEventProposedSlot(
                eventId=event_id,
                participantId=participant.id,
                startTime=starts_at,
                endTime=ends_at,
            )
        )

    # Generate candidate token for magic link
    candidate_token = str(uuid.uuid4())
    event.candidateToken = candidate_token
    db.add(event)

    await db.commit()

    # Send slot invitation email to candidate
    candidate = event.application.candidate
    candidate_email = candidate.email
    candidate_name = _candidate_display_name(event.application)
    interviewer_name = None
    if participant.member is not None and participant.member.user is not None:
        interviewer_name = participant.member.user.name or participant.member.user.email

    job_title = event.application.jobPosting.title if event.application.jobPosting else ""

    if candidate_email and interviewer_name:
        email_service = ResendEmailService()
        await email_service.send_interview_slot_invitation(
            to_email=candidate_email,
            candidate_name=candidate_name,
            interviewer_name=interviewer_name,
            job_title=job_title,
            organization_name=organization_name,
            candidate_token=candidate_token,
            is_reschedule=is_reschedule,
        )

    return InterviewAcceptResponse(
        eventId=event_id,
        status=participant.approvalStatus,
        meeting=None,
        candidateToken=candidate_token,
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

    # Find available team member with lowest active interview count
    existing_participant_ids = {p.memberId for p in (event.participants or [])}

    team_member_ids = await repository.get_primary_hiring_team_member_ids(
        organization_id,
        event.stage.jobPostingId,
        event.stage.id,
    )
    available_member_ids = [
        mid for mid in team_member_ids
        if mid not in rejected_member_ids and mid not in existing_participant_ids
    ]

    if not available_member_ids:
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
        available_member_ids,
    )
    new_member_id = min(
        available_member_ids,
        key=lambda mid: (active_counts.get(mid, 0), mid),
    )

    new_members = await repository.get_members_by_ids(organization_id, [new_member_id])
    new_member = new_members[0] if new_members else None
    if new_member is None:
        event.status = EventStatus.CANCELLED
        db.add(event)
        await db.commit()
        return InterviewRejectResponse(
            eventId=event.id,
            newInterviewerMemberId=None,
            status="UNASSIGNED",
            warnings=[],
        )

    new_participant = StageEventParticipant(
        eventId=event.id,
        memberId=new_member_id,
        role="INTERVIEWER",
        isBackup=False,
        approvalStatus="PENDING_ACCEPTANCE",
    )
    await repository.add_stage_event_participant(new_participant)
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
                    interviewerMemberId=new_member_id,
                    scheduledStartAt=event.scheduledStartAt,
                    durationMinutes=30,
                )
            ],
        )

    if new_member.user is not None:
        email_service = ResendEmailService()
        candidate_name = _candidate_display_name(event.application)
        starts_at_text = _meeting_time_text(event.scheduledStartAt) if event.scheduledStartAt else "To be scheduled"
        await email_service.send_stage_interview_assignment_to_interviewer(
            to_email=new_member.user.email,
            interviewer_name=new_member.user.name or new_member.user.email,
            candidate_name=candidate_name,
            candidate_email=event.application.candidate.email,
            stage_name=event.stage.name if event.stage else "Interview",
            organization_name=organization_name,
            starts_at_text=starts_at_text,
        )

    return InterviewRejectResponse(
        eventId=event.id,
        newInterviewerMemberId=new_member_id,
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
        proposed_slots = [
            PublicProposedSlotRead(
                id=slot.id,
                startTime=slot.startTime,
                endTime=slot.endTime,
            )
            for slot in sorted(
                event.proposedSlots or [],
                key=lambda item: item.startTime,
            )
        ]
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
                isBackup=False,
                meetingUrl=event.meetingUrl,
                stageDueDate=stage.dueDate if stage else None,
                proposedSlots=proposed_slots,
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
    if event.scheduledStartAt is None or event.scheduledEndAt is None:
        raise HTTPException(status_code=400, detail="Interview meeting is missing schedule metadata")

    application = event.application
    stage = event.stage
    candidate_name = _candidate_display_name(application) if application else "Candidate"
    stage_or_job_title = stage.name if stage else "Interview"

    if not event.meetingUrl:
        title = event.title or f"{stage_or_job_title} interview - {candidate_name}"
        description_parts = [
            f"Interview for {application.jobPosting.title if application and application.jobPosting else stage_or_job_title}",
            f"Candidate: {candidate_name}",
            f"Stage: {stage_or_job_title}",
        ]
        meeting = await GoogleCalendarService(db).create_meet_event(
            user_id=actor_user_id,
            summary=title,
            description="\n".join(description_parts),
            starts_at=event.scheduledStartAt,
            ends_at=event.scheduledEndAt,
        )
        event.meetingUrl = meeting.meeting_url
        event.googleCalendarEventId = meeting.event_id
        event.googleCalendarEventUrl = meeting.html_link

    event.status = EventStatus.ONGOING
    await repository.add_stage_event(event)
    await db.commit()

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

    feedback = next(
        (
            item
            for item in event.__dict__.get("feedbacks", [])
            if item.memberId == actor_member_id
        ),
        None,
    )
    if feedback is None:
        feedback = InterviewFeedback(
            organizationId=organization_id,
            eventId=event.id,
            memberId=actor_member_id,
        )
        db.add(feedback)
        await db.flush()

    note_body = body.notes.strip() if body.notes else ""
    feedback.notes = note_body or None
    if note_body:
        db.add(
            CandidateApplicationNote(
                organizationId=organization_id,
                applicationId=application_id,
                authorMemberId=actor_member_id,
                body=note_body,
            )
        )

    event.status = EventStatus.COMPLETED
    event.completedByMemberId = actor_member_id
    now = datetime.now(UTC)
    event.scheduledEndAt = now
    if not event.candidateToken:
        event.candidateToken = str(uuid.uuid4())
    db.add(event)
    await db.flush()

    # Send feedback request email to candidate
    try:
        candidate_email = event.application.candidate.email
        candidate_name_val = _candidate_name(event.application)
        job_title = event.application.jobPosting.title if event.application.jobPosting else ""
        stage_name = event.stage.name if event.stage else ""
        interviewer_name: str | None = None
        for participant in event.participants or []:
            if participant.member and participant.member.user:
                interviewer_name = participant.member.user.name or participant.member.user.email
                break

        email_service = ResendEmailService()
        await email_service.send_feedback_request(
            to_email=candidate_email,
            candidate_name=candidate_name_val,
            job_title=job_title,
            interviewer_name=interviewer_name,
            stage_name=stage_name,
            feedback_token=event.candidateToken,
        )
    except Exception:
        pass  # Non-blocking: feedback email failure should not break the completion

    await db.commit()
    return _serialize_interview_meeting(event)


def _candidate_name(application: CandidateApplication) -> str:
    return f"{application.candidate.firstName} {application.candidate.lastName}".strip()


async def get_candidate_slots_by_token(
    db: AsyncSession,
    token: str,
) -> dict:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_by_candidate_token(token)
    if event is None:
        raise HTTPException(status_code=404, detail="Interview not found or token expired")

    candidate_name = _candidate_display_name(event.application)
    job_title = event.application.jobPosting.title if event.application.jobPosting else ""

    # Get the participant who proposed slots
    participant = next(
        (p for p in (event.participants or []) if p.role == "INTERVIEWER" or p.role is None),
        None,
    )
    interviewer_name = "Interviewer"
    if participant is not None and participant.member is not None and participant.member.user is not None:
        interviewer_name = participant.member.user.name or participant.member.user.email

    slots = []
    for slot in (event.proposedSlots or []):
        if not slot.isSelectedByCandidate:
            slots.append({
                "id": slot.id,
                "startTime": slot.startTime,
                "endTime": slot.endTime,
            })

    return {
        "candidateName": candidate_name,
        "jobTitle": job_title,
        "interviewerName": interviewer_name,
        "candidateToken": token,
        "slots": slots,
    }


async def select_candidate_slot(
    db: AsyncSession,
    token: str,
    slot_id: str,
) -> dict:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_by_candidate_token(token)
    if event is None:
        raise HTTPException(status_code=404, detail="Interview not found or token expired")

    slot = next(
        (s for s in (event.proposedSlots or []) if s.id == slot_id),
        None,
    )
    if slot is None:
        raise HTTPException(status_code=404, detail="Slot not found")
    if slot.isSelectedByCandidate:
        raise HTTPException(status_code=400, detail="This slot has already been selected")

    slot.isSelectedByCandidate = True
    db.add(slot)

    duration_minutes = int((slot.endTime - slot.startTime).total_seconds() / 60)
    event.status = EventStatus.SCHEDULED
    event.scheduledStartAt = slot.startTime
    event.scheduledEndAt = slot.endTime
    db.add(event)

    participant = next(
        (p for p in (event.participants or []) if p.id == slot.participantId),
        None,
    )
    if participant is not None:
        participant.approvalStatus = "SCHEDULED"
        participant.scheduledTime = slot.startTime
        db.add(participant)

    await db.commit()

    # Create Google Meet meeting
    meeting = None
    if participant is not None:
        actor_user_id = None
        if participant.member is not None and participant.member.user is not None:
            actor_user_id = participant.member.user.id
        try:
            meeting = await create_interview_meeting(
                db,
                event.organizationId,
                participant.memberId,
                actor_user_id or participant.memberId,
                event.applicationId,
                InterviewMeetingCreateRequest(
                    mode="SCHEDULE",
                    scheduledStartAt=slot.startTime,
                    durationMinutes=duration_minutes,
                ),
            )
        except Exception:
            meeting = None

    # Send confirmation emails
    candidate = event.application.candidate
    candidate_email = candidate.email
    candidate_name = _candidate_display_name(event.application)
    job_title = event.application.jobPosting.title if event.application.jobPosting else ""

    interviewer_name = "Interviewer"
    interviewer_email = None
    if participant is not None and participant.member is not None and participant.member.user is not None:
        interviewer_name = participant.member.user.name or participant.member.user.email
        interviewer_email = participant.member.user.email

    starts_at_text = _meeting_time_text(slot.startTime)

    email_service = ResendEmailService()

    if candidate_email:
        await email_service.send_interview_slot_confirmation_to_candidate(
            to_email=candidate_email,
            candidate_name=candidate_name,
            interviewer_name=interviewer_name,
            job_title=job_title,
            starts_at_text=starts_at_text,
            meeting_url=meeting.meetingUrl if meeting else None,
        )

    if interviewer_email:
        await email_service.send_interview_slot_confirmation_to_interviewer(
            to_email=interviewer_email,
            interviewer_name=interviewer_name,
            candidate_name=candidate_name,
            job_title=job_title,
            starts_at_text=starts_at_text,
            meeting_url=meeting.meetingUrl if meeting else None,
        )

    return {"message": "Slot selected successfully"}


async def get_feedback_info_by_token(
    db: AsyncSession,
    token: str,
) -> FeedbackInfoResponse:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_by_candidate_token(token)
    if event is None:
        raise HTTPException(status_code=404, detail="Feedback link expired or invalid")

    candidate_name = _candidate_display_name(event.application)
    job_title = event.application.jobPosting.title if event.application.jobPosting else ""
    stage_name = event.stage.name if event.stage else ""

    interviewer_name: str | None = None
    participant = next(
        (p for p in (event.participants or []) if p.role == "INTERVIEWER" or p.role is None),
        None,
    )
    if participant is not None and participant.member is not None and participant.member.user is not None:
        interviewer_name = participant.member.user.name or participant.member.user.email

    return FeedbackInfoResponse(
        candidateName=candidate_name,
        jobTitle=job_title,
        interviewerName=interviewer_name,
        stageName=stage_name,
        interviewDate=event.scheduledStartAt or event.createdAt,
    )


async def submit_candidate_feedback(
    db: AsyncSession,
    token: str,
    body: FeedbackSubmitRequest,
) -> FeedbackSubmitResponse:
    repository = CandidatePipelineRepository(db)
    event = await repository.get_stage_event_by_candidate_token(token)
    if event is None:
        raise HTTPException(status_code=404, detail="Feedback link expired or invalid")

    note_body = body.body.strip()
    prefixed_body = f"[Candidate Feedback]\n{note_body}"

    db.add(
        CandidateApplicationNote(
            organizationId=event.organizationId,
            applicationId=event.applicationId,
            authorMemberId=event.completedByMemberId or event.createdByMemberId,
            body=prefixed_body,
        )
    )

    await db.commit()

    return FeedbackSubmitResponse(message="Feedback submitted successfully")



