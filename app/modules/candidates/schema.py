from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.recruitment import ApplicationSource

EvaluationType = Literal["NUMERIC", "TEXT", "CHECKBOX"]
InterviewMeetingMode = Literal["SCHEDULE", "START_NOW"]


class PipelineJobPostingRead(BaseModel):
    id: str
    title: str
    status: str


class CandidateSummaryRead(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: str
    phone: str | None
    linkedinUrl: str | None
    resumeUrl: str | None


class ApplicationInterviewMeetingRead(BaseModel):
    id: str
    status: Literal["PENDING", "ONGOING", "COMPLETED"]
    scheduledStartAt: datetime
    scheduledEndAt: datetime
    meetingUrl: str | None


class PipelineApplicationRead(BaseModel):
    id: str
    jobPostingId: str
    pipelineStageId: str
    currentStage: str
    candidate: CandidateSummaryRead
    score: int | None
    source: ApplicationSource
    appliedDate: datetime
    resumeUrl: str | None
    interviewMeeting: ApplicationInterviewMeetingRead | None = None


class StageEvaluationCategoryRead(BaseModel):
    id: str
    stageId: str
    name: str
    order: int


class StageEvaluationWorkspaceRead(BaseModel):
    id: str
    stageId: str
    googleSpreadsheetId: str
    googleSpreadsheetUrl: str
    googleSheetId: int | None
    googleSheetTitle: str
    createdByMemberId: str | None
    createdAt: datetime


class StageEvaluationCategoryInput(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    order: int | None = Field(default=None, ge=1)


class PipelineStageRead(BaseModel):
    id: str
    jobPostingId: str
    name: str
    order: int
    color: str | None
    isDefault: bool
    isFinal: bool
    isProtected: bool
    stageType: str
    meetingEnabled: bool
    offerLetterEnabled: bool
    evaluationEnabled: bool
    evaluationType: EvaluationType | None
    evaluationIncludeTotal: bool
    evaluationIncludeAnalysis: bool
    dueDate: datetime | None
    extendToNextWorkingDay: bool
    evaluationCategories: list[StageEvaluationCategoryRead]
    evaluationWorkspace: StageEvaluationWorkspaceRead | None
    applications: list[PipelineApplicationRead]


class PipelineBoardRead(BaseModel):
    jobPostingId: str
    stages: list[PipelineStageRead]


class MoveApplicationStageRequest(BaseModel):
    toStageId: str = Field(min_length=1)
    note: str | None = None


class PipelineStageCreateRequest(BaseModel):
    jobPostingId: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    afterStageId: str | None = None
    meetingEnabled: bool = False
    offerLetterEnabled: bool = False
    evaluationEnabled: bool = False
    evaluationType: EvaluationType | None = None
    evaluationIncludeTotal: bool = False
    evaluationIncludeAnalysis: bool = False
    dueDate: datetime | None = None
    extendToNextWorkingDay: bool = False
    evaluationCategories: list[StageEvaluationCategoryInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_stage_configuration(self) -> "PipelineStageCreateRequest":
        if self.meetingEnabled and self.dueDate is None:
            raise ValueError("Due date is required when online meeting is enabled")
        if self.dueDate is None:
            self.extendToNextWorkingDay = False
        if not self.evaluationEnabled:
            self.evaluationType = None
            self.evaluationIncludeTotal = False
            self.evaluationIncludeAnalysis = False
            self.evaluationCategories = []
        else:
            self.evaluationType = self.evaluationType or "NUMERIC"
        return self


class PipelineStageUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    order: int | None = Field(default=None, ge=1)
    meetingEnabled: bool | None = None
    offerLetterEnabled: bool | None = None
    evaluationEnabled: bool | None = None
    evaluationType: EvaluationType | None = None
    evaluationIncludeTotal: bool | None = None
    evaluationIncludeAnalysis: bool | None = None
    dueDate: datetime | None = None
    dueDateEnabled: bool | None = None
    extendToNextWorkingDay: bool | None = None
    evaluationCategories: list[StageEvaluationCategoryInput] | None = None

    @model_validator(mode="after")
    def validate_stage_configuration(self) -> "PipelineStageUpdateRequest":
        if self.meetingEnabled is True and self.dueDateEnabled is False:
            self.dueDateEnabled = True
        if self.dueDateEnabled is False:
            self.dueDate = None
            self.extendToNextWorkingDay = False
        if self.evaluationEnabled is False:
            self.evaluationType = None
            self.evaluationIncludeTotal = False
            self.evaluationIncludeAnalysis = False
            self.evaluationCategories = []
        elif self.evaluationEnabled is True:
            self.evaluationType = self.evaluationType or "NUMERIC"
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
    def validate_schedule(self) -> "InterviewMeetingCreateRequest":
        if self.mode == "SCHEDULE" and self.scheduledStartAt is None:
            raise ValueError("Start time is required when scheduling an interview")
        return self


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


class CandidateApplicationDetailRead(BaseModel):
    id: str
    jobPostingId: str
    jobPostingTitle: str
    pipelineStageId: str
    currentStage: str
    candidate: CandidateSummaryRead
    source: ApplicationSource
    score: int | None
    notes: str | None
    resumeUrl: str | None
    appliedAt: datetime
    lastActivityAt: datetime
    stageHistory: list[PipelineStageHistoryRead]
