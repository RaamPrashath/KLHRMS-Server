from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.recruitment import ApplicationSource

InterviewMeetingMode = Literal["SCHEDULE", "START_NOW"]


class PipelineJobPostingRead(BaseModel):
    id: str
    slug: str
    title: str
    status: str
    requisitionId: str | None = None
    candidateCount: int = 0
    stageCount: int = 0
    priority: str | None = None
    openings: int | None = None


class CandidateSummaryRead(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: str
    phone: str | None
    linkedinUrl: str | None
    portfolioUrl: str | None
    currentCompany: str | None
    currentTitle: str | None
    totalExperience: str | None
    resumeUrl: str | None
    image: str | None = None


class ApplicationInterviewMeetingRead(BaseModel):
    id: str
    status: Literal["PENDING", "ONGOING", "COMPLETED", "CANCELLED", "RESCHEDULED"]
    scheduledStartAt: datetime
    scheduledEndAt: datetime
    meetingUrl: str | None
    interviewerName: str | None = None
    completedAt: datetime | None = None


class PipelineApplicationRead(BaseModel):
    id: str
    jobPostingId: str
    pipelineStageId: str
    currentStage: str
    candidate: CandidateSummaryRead
    source: ApplicationSource
    appliedDate: datetime
    lastMovedAt: datetime | None
    status: str
    resumeUrl: str | None
    aiScore: int | None = None
    aiAnalysisStatus: str | None = None
    aiEvaluationStatus: str | None = None
    isFlaggedForCheating: bool = False
    aiFailedKnockouts: list[dict] = Field(default_factory=list)
    interviewMeeting: ApplicationInterviewMeetingRead | None = None
    currentAssignment: StageWorkspaceAssignmentRead | None = None


class InterviewMeetingStartRequest(BaseModel):
    pass


class InterviewMeetingCompleteRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class PipelineStageRead(BaseModel):
    id: str
    jobPostingId: str
    name: str
    slug: str
    order: float
    color: str | None
    isDefault: bool
    isFinal: bool
    isProtected: bool
    stageType: str
    meetingEnabled: bool
    offerLetterEnabled: bool
    dueDate: datetime | None
    completedAt: datetime | None = None
    extendToNextWorkingDay: bool
    applications: list[PipelineApplicationRead]


class PipelineBoardRead(BaseModel):
    jobPostingId: str
    stages: list[PipelineStageRead]


class StageWorkspaceInterviewerRead(BaseModel):
    memberId: str
    name: str
    email: str
    department: str | None = None


class StageWorkspaceAssignmentRead(BaseModel):
    eventId: str
    interviewer: StageWorkspaceInterviewerRead | None
    scheduledStartAt: datetime | None
    scheduledEndAt: datetime | None
    meetLink: str | None = None
    status: str
    emailSentAt: datetime | None


class StageWorkspaceCandidateRead(BaseModel):
    applicationId: str
    candidate: CandidateSummaryRead
    jobTitle: str
    source: ApplicationSource
    appliedAt: datetime
    currentAssignment: StageWorkspaceAssignmentRead | None = None


class StageWorkspaceRead(BaseModel):
    stage: PipelineStageRead
    jobPosting: PipelineJobPostingRead
    candidateCount: int
    candidates: list[StageWorkspaceCandidateRead]
    teamMembers: list[StageWorkspaceInterviewerRead]
    assignmentTeamId: str | None = None


class InterviewerSearchResponse(BaseModel):
    items: list[StageWorkspaceInterviewerRead]


class StageInterviewAssignmentInput(BaseModel):
    applicationId: str = Field(min_length=1)
    interviewerMemberId: str = Field(min_length=1)
    scheduledStartAt: datetime | None = None
    durationMinutes: int = Field(default=30, ge=15, le=240)
    meetLink: str | None = Field(default=None, max_length=2048)


class StageInterviewWarningRead(BaseModel):
    applicationId: str
    interviewerMemberId: str
    messages: list[str]


class StageInterviewWarningRequest(BaseModel):
    assignments: list[StageInterviewAssignmentInput] = Field(default_factory=list)
    jobPostingId: str | None = None


class StageInterviewWarningResponse(BaseModel):
    warnings: list[StageInterviewWarningRead]


class StageInterviewAssignmentRequest(BaseModel):
    assignments: list[StageInterviewAssignmentInput] = Field(min_length=1)
    jobPostingId: str | None = None


class StageInterviewAssignmentResponse(BaseModel):
    assignedCount: int
    warnings: list[StageInterviewWarningRead]


class TeamDistributionRequest(BaseModel):
    hiringTeamId: str = Field(min_length=1)
    strategy: Literal["ROUND_ROBIN"] = "ROUND_ROBIN"
    applicationIds: list[str] = Field(min_length=1)
    scheduledStartAt: datetime | None = None
    durationMinutes: int = Field(default=30, ge=15, le=240)
    ignoreWarnings: bool = False


class TeamDistributionResponse(BaseModel):
    assignedCount: int
    warnings: list[StageInterviewWarningRead]


class InterviewMoveRequest(BaseModel):
    newInterviewerMemberId: str = Field(min_length=1)


class InterviewMoveResponse(BaseModel):
    eventId: str
    newInterviewerMemberId: str
    status: str


class ReshuffleRequest(BaseModel):
    newInterviewerMemberId: str | None = None


class ReshuffleResponse(BaseModel):
    eventId: str
    newInterviewerMemberId: str
    warnings: list[StageInterviewWarningRead]


class InterviewAcceptRequest(BaseModel):
    scheduledStartAt: datetime | None = None
    durationMinutes: int = Field(default=30, ge=15, le=240)


class InterviewRejectResponse(BaseModel):
    eventId: str
    newInterviewerMemberId: str | None
    status: Literal["ESCALATED", "UNASSIGNED"]
    warnings: list[StageInterviewWarningRead]


class MyInterviewRead(BaseModel):
    eventId: str
    applicationId: str
    stageId: str
    stageName: str
    candidate: CandidateSummaryRead
    jobTitle: str
    jobPostingId: str
    jobSlug: str | None = None
    scheduledStartAt: datetime | None
    scheduledEndAt: datetime | None
    status: str
    role: str
    isBackup: bool
    meetingUrl: str | None = None
    stageDueDate: datetime | None = None


class MyInterviewListResponse(BaseModel):
    items: list[MyInterviewRead]


class ReassignmentRequestCreate(BaseModel):
    eventId: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=1000)


class MoveApplicationStageRequest(BaseModel):
    toStageId: str = Field(min_length=1)
    note: str | None = None


class PipelineStageCreateRequest(BaseModel):
    jobPostingId: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=50)
    afterStageId: str | None = None
    stageType: str = Field(default="DEFAULT", min_length=1, max_length=32)
    dueDate: datetime | None = None

    @model_validator(mode="after")
    def validate_stage_configuration(self) -> PipelineStageCreateRequest:
        self.stageType = self.stageType.strip().upper()
        return self


class PipelineStageUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    order: float | None = Field(default=None)
    stageType: str | None = Field(default=None, min_length=1, max_length=32)
    dueDate: datetime | None = None
    dueDateEnabled: bool | None = None

    @model_validator(mode="after")
    def validate_stage_configuration(self) -> PipelineStageUpdateRequest:
        if self.stageType is not None:
            self.stageType = self.stageType.strip().upper()
        if self.dueDateEnabled is False:
            self.dueDate = None
        return self


class PipelineStageHistoryRead(BaseModel):
    id: str
    fromStageId: str | None
    fromStageName: str | None
    toStageId: str
    toStageName: str | None
    movedByMemberId: str | None
    movedByName: str | None
    note: str | None
    createdAt: datetime


class InterviewMeetingCreateRequest(BaseModel):
    mode: InterviewMeetingMode
    scheduledStartAt: datetime | None = None
    durationMinutes: int = Field(default=30, ge=15, le=240)
    title: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_schedule(self) -> InterviewMeetingCreateRequest:
        if self.mode == "SCHEDULE" and self.scheduledStartAt is None:
            raise ValueError("Start time is required when scheduling an interview")
        return self


class InterviewMeetingUpdateRequest(BaseModel):
    scheduledStartAt: datetime
    durationMinutes: int = Field(default=30, ge=15, le=240)
    title: str | None = Field(default=None, max_length=160)
    notes: str | None = Field(default=None, max_length=1000)


class InterviewMeetingRead(BaseModel):
    id: str
    applicationId: str
    stageId: str
    title: str
    status: str
    scheduledStartAt: datetime
    scheduledEndAt: datetime
    meetingUrl: str | None
    googleCalendarEventId: str | None
    googleCalendarEventUrl: str | None
    emailSentAt: datetime | None
    createdAt: datetime


class InterviewAcceptResponse(BaseModel):
    eventId: str
    status: str
    meeting: InterviewMeetingRead | None = None


class CandidateApplicationNoteRead(BaseModel):
    id: str
    authorMemberId: str
    authorName: str
    authorEmail: str | None
    body: str
    canEdit: bool
    createdAt: datetime
    updatedAt: datetime


class CandidateApplicationNoteCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class CandidateApplicationNoteUpdateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class InterviewParticipantRead(BaseModel):
    memberId: str
    name: str
    email: str | None
    role: str | None
    isBackup: bool


class InterviewFeedbackRead(BaseModel):
    id: str
    memberId: str
    memberName: str
    outcome: str
    notes: str | None
    createdAt: datetime


class ApplicationInterviewEventRead(BaseModel):
    id: str
    stageId: str
    stageName: str | None
    title: str
    status: str
    scheduledStartAt: datetime | None
    scheduledEndAt: datetime | None
    completedAt: datetime | None
    durationMinutes: int | None
    meetingUrl: str | None
    createdByName: str | None
    completedByName: str | None
    participants: list[InterviewParticipantRead]
    feedbacks: list[InterviewFeedbackRead]
    notes: str | None
    createdAt: datetime


class CandidateApplicationDetailRead(BaseModel):
    id: str
    jobPostingId: str
    jobPostingTitle: str
    pipelineStageId: str
    currentStage: str
    candidate: CandidateSummaryRead
    source: ApplicationSource
    coverLetter: str | None
    internalNotes: str | None
    status: str
    resumeUrl: str | None
    appliedAt: datetime
    lastActivityAt: datetime
    stageHistory: list[PipelineStageHistoryRead]
    interviewEvents: list[ApplicationInterviewEventRead] = Field(default_factory=list)
    notes: list[CandidateApplicationNoteRead] = Field(default_factory=list)


class CandidateApplicationUpdateRequest(BaseModel):
    internalNotes: str | None = Field(default=None, max_length=5000)
    resumeUrl: str | None = Field(default=None, max_length=4096)
