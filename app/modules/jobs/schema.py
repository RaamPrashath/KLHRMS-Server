from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.models.recruitment import (
    EmploymentType,
    JobRequisitionStatus,
    RequisitionApprovalDecision,
)

PipelineStageType = Literal["DEFAULT", "INTERVIEW", "OFFER", "HIRED", "REJECTED"]

_SALARY_UNITS = {
    "crore": 10000000,
    "crores": 10000000,
    "cr": 10000000,
    "lakh": 100000,
    "lakhs": 100000,
    "lac": 100000,
    "lacs": 100000,
    "l": 100000,
    "thousand": 1000,
    "thousands": 1000,
    "k": 1000,
}


def parse_salary_amount(value: Any) -> float | None:
    if value is None or isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        raise ValueError("Salary must be a valid amount")

    normalized = (
        value.strip()
        .lower()
        .replace(",", "")
        .replace("₹", "")
    )
    if not normalized:
        return None

    token_pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|lakh|lac|l|thousands?|k)?"
    )
    total = 0.0
    consumed: list[str] = []
    for match in token_pattern.finditer(normalized):
        amount = float(match.group(1))
        unit = match.group(2) or ""
        total += amount * _SALARY_UNITS.get(unit, 1)
        consumed.append(match.group(0))

    compact_consumed = "".join(consumed).replace(" ", "")
    compact_normalized = normalized.replace(" ", "")
    if not consumed or compact_consumed != compact_normalized:
        raise ValueError("Salary must be a valid amount")
    return round(total, 2)


class JobRequisitionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    departmentId: str | None = None
    employmentType: EmploymentType = EmploymentType.FULL_TIME
    openings: int = Field(default=1, ge=1)

    hiringReason: str | None = None
    priority: str = "MEDIUM"
    replacementForId: str | None = None
    businessJustification: str | None = None

    salaryMin: float | None = None
    salaryMax: float | None = None
    currency: str = Field(default="INR", min_length=1, max_length=10)
    salaryVisibility: str = "INTERNAL_ONLY"

    skills: list[str] = Field(default_factory=list)
    experienceLevel: str | None = None
    minExperience: int | None = None
    education: str | None = None
    certifications: list[str] = Field(default_factory=list)
    knockoutRule: str | None = Field(default=None, max_length=2000)

    roleSummary: str | None = None
    responsibilities: str | None = None
    requirementsRich: str | None = None
    benefits: str | None = None
    aboutTeam: str | None = None

    description: str | None = None
    requirements: str | None = None

    location: str | None = None
    isRemote: bool = False
    targetDate: date | None = None

    @field_validator("skills", "certifications")
    @classmethod
    def normalize_list_fields(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

    @field_validator("salaryMax")
    @classmethod
    def validate_salary_range(cls, value: float | None, info: ValidationInfo) -> float | None:
        salary_min = info.data.get("salaryMin")
        if value is not None and salary_min is not None and value < salary_min:
            raise ValueError("salaryMax must be greater than or equal to salaryMin")
        return value

    @field_validator("salaryMin", "salaryMax", mode="before")
    @classmethod
    def parse_salary(cls, value: Any) -> float | None:
        return parse_salary_amount(value)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        if value not in allowed:
            raise ValueError(f"priority must be one of {allowed}")
        return value

    @field_validator("hiringReason")
    @classmethod
    def validate_hiring_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {
            "NEW_ROLE",
            "REPLACEMENT",
            "TEAM_EXPANSION",
            "URGENT_REQUIREMENT",
            "INTERNAL_TRANSFER",
            "CLIENT_REQUIREMENT",
        }
        if value not in allowed:
            raise ValueError(f"hiringReason must be one of {allowed}")
        return value

    @field_validator("salaryVisibility")
    @classmethod
    def validate_salary_visibility(cls, value: str) -> str:
        allowed = {"INTERNAL_ONLY", "PUBLIC"}
        if value not in allowed:
            raise ValueError(f"salaryVisibility must be one of {allowed}")
        return value


class JobRequisitionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    departmentId: str | None = None
    employmentType: EmploymentType | None = None
    openings: int | None = Field(default=None, ge=1)

    hiringReason: str | None = None
    priority: str | None = None
    replacementForId: str | None = None
    businessJustification: str | None = None

    salaryMin: float | None = None
    salaryMax: float | None = None
    currency: str | None = Field(default=None, min_length=1, max_length=10)
    salaryVisibility: str | None = None

    skills: list[str] | None = None
    experienceLevel: str | None = None
    minExperience: int | None = None
    education: str | None = None
    certifications: list[str] | None = None
    knockoutRule: str | None = Field(default=None, max_length=2000)

    roleSummary: str | None = None
    responsibilities: str | None = None
    requirementsRich: str | None = None
    benefits: str | None = None
    aboutTeam: str | None = None

    description: str | None = None
    requirements: str | None = None
    location: str | None = None
    isRemote: bool | None = None
    targetDate: date | None = None

    @field_validator("skills", "certifications")
    @classmethod
    def normalize_optional_list_fields(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.strip() for item in value if item.strip()]

    @field_validator("salaryMin", "salaryMax", mode="before")
    @classmethod
    def parse_salary(cls, value: Any) -> float | None:
        return parse_salary_amount(value)

    @field_validator("salaryMax")
    @classmethod
    def validate_salary_range(cls, value: float | None, info: ValidationInfo) -> float | None:
        salary_min = info.data.get("salaryMin")
        if value is not None and salary_min is not None and value < salary_min:
            raise ValueError("salaryMax must be greater than or equal to salaryMin")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        if value not in allowed:
            raise ValueError(f"priority must be one of {allowed}")
        return value

    @field_validator("hiringReason")
    @classmethod
    def validate_hiring_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {
            "NEW_ROLE",
            "REPLACEMENT",
            "TEAM_EXPANSION",
            "URGENT_REQUIREMENT",
            "INTERNAL_TRANSFER",
            "CLIENT_REQUIREMENT",
        }
        if value not in allowed:
            raise ValueError(f"hiringReason must be one of {allowed}")
        return value

    @field_validator("salaryVisibility")
    @classmethod
    def validate_salary_visibility(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {"INTERNAL_ONLY", "PUBLIC"}
        if value not in allowed:
            raise ValueError(f"salaryVisibility must be one of {allowed}")
        return value


class JobRequisitionDecisionRequest(BaseModel):
    comment: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    departmentId: str | None = None
    employmentType: EmploymentType | None = None
    openings: int | None = Field(default=None, ge=1)
    salaryMin: float | None = None
    salaryMax: float | None = None
    currency: str | None = Field(default=None, min_length=1, max_length=10)
    description: str | None = None
    requirements: str | None = None
    skills: list[str] | None = None
    location: str | None = None
    isRemote: bool | None = None
    targetDate: date | None = None
    roleSummary: str | None = None
    responsibilities: str | None = None
    requirementsRich: str | None = None
    benefits: str | None = None
    aboutTeam: str | None = None
    hiringReason: str | None = None
    priority: str | None = None
    businessJustification: str | None = None
    experienceLevel: str | None = None
    minExperience: int | None = None
    education: str | None = None
    certifications: list[str] | None = None
    knockoutRule: str | None = Field(default=None, max_length=2000)

    @field_validator("skills", "certifications")
    @classmethod
    def normalize_optional_list_fields(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.strip() for item in value if item.strip()]

    @field_validator("salaryMin", "salaryMax", mode="before")
    @classmethod
    def parse_decision_salary(cls, value: Any) -> float | None:
        return parse_salary_amount(value)

    @field_validator("salaryMax")
    @classmethod
    def validate_decision_salary_range(cls, value: float | None, info: ValidationInfo) -> float | None:
        salary_min = info.data.get("salaryMin")
        if value is not None and salary_min is not None and value < salary_min:
            raise ValueError("salaryMax must be greater than or equal to salaryMin")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
        if value not in allowed:
            raise ValueError(f"priority must be one of {allowed}")
        return value

    @field_validator("hiringReason")
    @classmethod
    def validate_hiring_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        allowed = {
            "NEW_ROLE",
            "REPLACEMENT",
            "TEAM_EXPANSION",
            "URGENT_REQUIREMENT",
            "INTERNAL_TRANSFER",
            "CLIENT_REQUIREMENT",
        }
        if value not in allowed:
            raise ValueError(f"hiringReason must be one of {allowed}")
        return value


class JobLookupOptionRead(BaseModel):
    id: str
    label: str
    email: str | None = None


class JobFormMetaRead(BaseModel):
    members: list[JobLookupOptionRead]
    departments: list[JobLookupOptionRead]


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
    hiringReason: str | None
    priority: str
    replacementForId: str | None
    replacementForName: str | None
    businessJustification: str | None
    salaryVisibility: str
    experienceLevel: str | None
    minExperience: int | None
    education: str | None
    certifications: list[str]
    knockoutRule: str | None
    roleSummary: str | None
    responsibilities: str | None
    requirementsRich: str | None
    benefits: str | None
    aboutTeam: str | None
    requisitionNumber: int | None
    requisitionLabel: str | None
    canEdit: bool
    approvalSummary: JobRequisitionApprovalSummaryRead
    currentUserApprovalDecision: RequisitionApprovalDecision | None
    currentUserCanApprove: bool
    canSubmit: bool
    approvals: list[JobRequisitionApprovalRead]


class JobRequisitionDetailRead(JobRequisitionListItemRead):
    pass


class RequisitionKnockoutRulesRead(BaseModel):
    explicitRule: str | None = None


class RequisitionScoringWeightsRead(BaseModel):
    experiencePointsPerYear: int = 0
    maxExperiencePoints: int = 0
    maxSkillPoints: int = 0
    skillWeights: dict[str, int] = Field(default_factory=dict)
    educationPoints: int = 0
    educationKeywords: list[str] = Field(default_factory=list)
    certificationWeights: dict[str, int] = Field(default_factory=dict)
    totalPossiblePoints: int = 0


class JobRequisitionRulesRead(BaseModel):
    id: str
    organizationId: str
    requisitionId: str
    jobPostingId: str | None
    rulesVersion: str
    knockoutRules: RequisitionKnockoutRulesRead
    scoringWeights: RequisitionScoringWeightsRead
    sourceSnapshot: dict[str, Any]
    createdAt: datetime
    updatedAt: datetime


class RequisitionAiAnalysisStatsRead(BaseModel):
    totalApplications: int = 0
    analyzedApplications: int = 0
    pendingApplications: int = 0
    flaggedCandidates: int = 0
    recommendedCandidates: int = 0
    averageScore: float | None = None


class RequisitionAiCandidateRead(BaseModel):
    applicationId: str
    candidateId: str
    candidateName: str
    email: str
    aiScore: int | None = None
    aiAnalysisStatus: str | None = None
    evaluationStatus: str | None = None
    isFlaggedForCheating: bool = False
    failedKnockouts: list[dict[str, Any]] = Field(default_factory=list)


class JobRequisitionAiAnalysisRead(BaseModel):
    requisitionId: str
    jobPostingId: str | None = None
    rulesMissing: bool
    rules: JobRequisitionRulesRead | None = None
    stats: RequisitionAiAnalysisStatsRead
    candidates: list[RequisitionAiCandidateRead] = Field(default_factory=list)


class StageEvaluationCategoryInput(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    type: Literal["NUMERIC", "TEXT", "CHECKBOX"] = "NUMERIC"
    maxScore: int | None = Field(default=None, ge=1)
    order: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def strip_category_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Category name is required")
        return stripped


class StageEvaluationCategoryRead(BaseModel):
    id: str
    stageId: str
    name: str
    type: str
    maxScore: int | None = None
    order: int


class CreatePipelineStageRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    stageType: PipelineStageType = "DEFAULT"
    evaluationEnabled: bool = False
    sheetEnabled: bool = False
    evaluationType: Literal["NUMERIC", "TEXT", "CHECKBOX"] | None = None
    evaluationIncludeTotal: bool = False
    evaluationIncludeAnalysis: bool = False
    dueDate: datetime | None = None
    extendToNextWorkingDay: bool = False
    evaluationCategories: list[StageEvaluationCategoryInput] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_stage_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Stage name is required")
        return stripped

    def model_post_init(self, __context: Any) -> None:
        if not self.evaluationEnabled:
            self.evaluationType = None
            self.evaluationIncludeTotal = False
            self.evaluationIncludeAnalysis = False
            self.evaluationCategories = []
        elif self.evaluationType is None:
            self.evaluationType = "NUMERIC"


class ImportPipelineRequest(BaseModel):
    sourceJobPostingId: str = Field(min_length=1)


class PipelineStageRead(BaseModel):
    id: str
    jobPostingId: str
    name: str
    slug: str
    order: float
    color: str | None
    isDefault: bool
    isFinal: bool
    stageType: str
    meetingEnabled: bool
    offerLetterEnabled: bool
    evaluationEnabled: bool
    sheetEnabled: bool = False
    evaluationType: str | None
    evaluationIncludeTotal: bool
    evaluationIncludeAnalysis: bool
    dueDate: datetime | None
    extendToNextWorkingDay: bool
    evaluationCategories: list[StageEvaluationCategoryRead]


class PipelineBoardRead(BaseModel):
    jobPostingId: str
    stages: list[PipelineStageRead]


class ImportableJobPostingRead(BaseModel):
    id: str
    title: str
    departmentName: str | None
    stageCount: int
    stages: list[PipelineStageRead]


class PublicJobPostingListItemRead(BaseModel):
    id: str
    organizationId: str
    organizationName: str
    organizationSlug: str
    title: str
    description: str
    requirements: str | None
    roleSummary: str | None = None
    responsibilities: str | None = None
    requirementsRich: str | None = None
    benefits: str | None = None
    aboutTeam: str | None = None
    requisitionId: str | None = None
    location: str | None = None
    employmentType: str | None = None
    openings: int | None = None
    salaryMin: float | None = None
    salaryMax: float | None = None
    currency: str | None = None
    isRemote: bool = False
    targetDate: datetime | None = None
    skills: list[str] = Field(default_factory=list)
    experienceLevel: str | None = None
    minExperience: int | None = None
    education: str | None = None
    certifications: list[str] = Field(default_factory=list)
    departmentName: str | None = None
    hiringReason: str | None = None
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
