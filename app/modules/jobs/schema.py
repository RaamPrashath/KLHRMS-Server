from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.models.recruitment import (
    EmploymentType,
    JobRequisitionStatus,
    RequisitionApprovalDecision,
)


class JobRequisitionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    departmentId: str | None = None
    employmentType: EmploymentType = EmploymentType.FULL_TIME
    openings: int = Field(default=1, ge=1)
    salaryMin: float | None = None
    salaryMax: float | None = None
    currency: str = Field(default="INR", min_length=1, max_length=10)
    description: str | None = None
    requirements: str | None = None
    skills: list[str] = Field(default_factory=list)
    location: str | None = None
    isRemote: bool = False
    targetDate: date | None = None

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: list[str]) -> list[str]:
        return [skill.strip() for skill in value if skill.strip()]

    @field_validator("salaryMax")
    @classmethod
    def validate_salary_range(cls, value: float | None, info: ValidationInfo) -> float | None:
        salary_min = info.data.get("salaryMin")
        if value is not None and salary_min is not None and value < salary_min:
            raise ValueError("salaryMax must be greater than or equal to salaryMin")
        return value


class JobRequisitionDecisionRequest(BaseModel):
    comment: str | None = None


class JobRequisitionApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    approverId: str
    approverName: str | None
    decision: RequisitionApprovalDecision
    comment: str | None
    decidedAt: datetime | None
    createdAt: datetime


class JobRequisitionApprovalSummaryRead(BaseModel):
    approvedCount: int
    rejectedCount: int
    pendingCount: int
    totalCount: int


class JobRequisitionListItemRead(BaseModel):
    id: str
    title: str
    departmentId: str | None
    departmentName: str | None
    employmentType: EmploymentType
    openings: int
    salaryMin: float | None
    salaryMax: float | None
    currency: str
    description: str | None
    requirements: str | None
    skills: list[str]
    location: str | None
    isRemote: bool
    raisedById: str
    raisedByName: str | None
    targetDate: datetime | None
    status: JobRequisitionStatus
    createdAt: datetime
    updatedAt: datetime
    closedAt: datetime | None
    approvalSummary: JobRequisitionApprovalSummaryRead
    currentUserApprovalDecision: RequisitionApprovalDecision | None
    currentUserCanApprove: bool
    canSubmit: bool
    approvals: list[JobRequisitionApprovalRead]


class JobRequisitionDetailRead(JobRequisitionListItemRead):
    pass


class PublicJobPostingListItemRead(BaseModel):
    id: str
    organizationId: str
    organizationName: str
    organizationSlug: str
    title: str
    description: str
    requirements: str | None
    location: str | None = None
    employmentType: str | None = None
    openings: int | None = None
    salaryMin: float | None = None
    salaryMax: float | None = None
    currency: str | None = None
    isRemote: bool = False
    targetDate: datetime | None = None
    skills: list[str] = Field(default_factory=list)
    publishedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime


class PublicJobPostingDetailRead(PublicJobPostingListItemRead):
    pass


class PublicJobApplicationRequest(BaseModel):
    firstName: str = Field(min_length=1, max_length=255)
    lastName: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    linkedinUrl: str | None = Field(default=None, max_length=2048)
    resumeUrl: str = Field(min_length=1, max_length=4096)
    coverLetter: str | None = None

    @field_validator("firstName", "lastName", "resumeUrl")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field is required")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("A valid email is required")
        return normalized

    @field_validator("phone", "linkedinUrl", "coverLetter")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PublicJobApplicationRead(BaseModel):
    applicationId: str
    candidateId: str
    jobPostingId: str
    organizationId: str
    pipelineStageId: str
