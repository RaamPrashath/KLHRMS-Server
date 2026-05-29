from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OnboardingStageSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    stageType: str
    order: float


class OnboardingJobPostingSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str


class OnboardingCandidateSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    firstName: str
    lastName: str
    email: str | None = None
    resumeUrl: str | None = None


class OnboardingRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    applicationId: str
    status: str
    aadharUrl: str | None = None
    panUrl: str | None = None
    assignedRoleId: str | None = None
    assignedEmail: str | None = None
    tokenSentAt: datetime | None = None
    submittedAt: datetime | None = None
    credentialsSentAt: datetime | None = None
    credentialsEmailError: str | None = None
    createdAt: datetime
    updatedAt: datetime


class AcceptedOnboardingCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    applicationId: str
    candidate: OnboardingCandidateSummaryRead
    appliedAt: datetime
    source: str
    onboardingStatus: str
    latestOnboarding: OnboardingRecordRead | None = None


class AcceptedOnboardingWorkspaceRead(BaseModel):
    stage: OnboardingStageSummaryRead
    jobPosting: OnboardingJobPostingSummaryRead
    candidateCount: int
    candidates: list[AcceptedOnboardingCandidateRead]
    onboardStage: OnboardingStageSummaryRead | None = None


class OnboardWorkspaceCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    applicationId: str
    candidate: OnboardingCandidateSummaryRead
    appliedAt: datetime
    source: str
    onboardingStatus: str
    onboardingRecordId: str | None = None
    aadharUrl: str | None = None
    panUrl: str | None = None
    assignedRoleId: str | None = None
    assignedEmail: str | None = None
    credentialsSentAt: datetime | None = None
    credentialsEmailError: str | None = None


class OnboardWorkspaceRead(BaseModel):
    stage: OnboardingStageSummaryRead
    jobPosting: OnboardingJobPostingSummaryRead
    candidateCount: int
    candidates: list[OnboardWorkspaceCandidateRead]


class OnboardingSendRequest(BaseModel):
    applicationIds: list[str] = Field(min_length=1)


class OnboardingSendResponse(BaseModel):
    requestedCount: int


class OnboardingAssignCredentialsRequest(BaseModel):
    roleId: str = Field(min_length=1)
    email: str = Field(min_length=1, max_length=320)


class OnboardingAssignCredentialsResponse(BaseModel):
    onboardingId: str
    status: str


class OnboardingPublicRead(BaseModel):
    token: str
    candidateName: str
    jobTitle: str
    organizationName: str
    status: str
    submittedAt: datetime | None = None


class OnboardingSubmitDocumentsRequest(BaseModel):
    aadharBase64: str
    aadharFileName: str = "aadhar"
    panBase64: str
    panFileName: str = "pan"


class OnboardingSubmitDocumentsResponse(BaseModel):
    status: str
    message: str
