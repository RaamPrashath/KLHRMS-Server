from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.recruitment import ApplicationSource


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


class PipelineStageRead(BaseModel):
    id: str
    jobPostingId: str
    name: str
    order: int
    color: str | None
    isDefault: bool
    isFinal: bool
    isProtected: bool
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


class PipelineStageUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    order: int | None = Field(default=None, ge=1)


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
