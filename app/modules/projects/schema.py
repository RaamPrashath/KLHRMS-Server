from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

PROJECT_STATUSES = {"ACTIVE", "ON_HOLD", "COMPLETED", "CANCELLED"}


class ProjectFilters(BaseModel):
    search: str | None = None
    status: str | None = None
    billable: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.upper().replace("-", "_")
        if normalized not in PROJECT_STATUSES:
            raise ValueError("Invalid project status")
        return normalized


class ProjectMemberAssignBulkRequest(BaseModel):
    memberIds: list[str]


class ProjectMemberAssignRequest(BaseModel):
    memberId: str
    role: str | None = Field(default=None, max_length=120)
    allocatedHours: float | None = Field(default=None, ge=0)


class ProjectTaskCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ProjectUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    teamId: str | None = None
    clientName: str | None = Field(default=None, max_length=255)
    budget: float | None = Field(default=None, ge=0)
    budgetedHours: float | None = Field(default=None, ge=0)
    startDate: date | None = None
    endDate: date | None = None
    status: str = Field(default="ACTIVE")
    billable: bool = True
    description: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.upper().replace("-", "_")
        if normalized not in PROJECT_STATUSES:
            raise ValueError("Invalid project status")
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> ProjectUpsertRequest:
        if self.startDate and self.endDate and self.endDate < self.startDate:
            raise ValueError("End date must be on or after the start date")
        return self


class ProjectMemberSummary(BaseModel):
    id: str
    memberId: str
    name: str | None
    email: str | None
    role: str | None
    allocatedHours: float | None


class ProjectTaskSummary(BaseModel):
    id: str
    name: str
    createdAt: datetime


class ProjectCapacitySummary(BaseModel):
    budgetedHours: float | None
    allocatedHours: float
    loggedHours: float | None
    remainingHours: float | None
    warning: str | None


class ProjectSummary(BaseModel):
    id: str
    name: str
    teamId: str | None
    teamName: str | None
    clientName: str | None
    budget: float | None
    budgetedHours: float | None
    startDate: date | None
    endDate: date | None
    status: str
    billable: bool
    memberCount: int
    taskCount: int
    allocatedHours: float
    capacity: ProjectCapacitySummary
    createdAt: datetime
    updatedAt: datetime


class ProjectDetailResponse(ProjectSummary):
    description: str | None
    members: list[ProjectMemberSummary]
    tasks: list[ProjectTaskSummary]


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]
    total: int
    page: int
    page_size: int


class ProjectLookupOption(BaseModel):
    id: str
    label: str
    email: str | None = None


class ProjectMetaResponse(BaseModel):
    members: list[ProjectLookupOption]
    departments: list[ProjectLookupOption]
    teams: list[ProjectLookupOption]
