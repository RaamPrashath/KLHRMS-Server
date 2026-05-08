from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

DEPARTMENT_STATUSES = {"ACTIVE", "INACTIVE"}
TEAM_STATUSES = {"ACTIVE", "INACTIVE"}


class DepartmentUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    headMemberId: str | None = None
    parentDepartmentId: str | None = None
    status: str = Field(default="ACTIVE")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in DEPARTMENT_STATUSES:
            raise ValueError("Invalid department status")
        return normalized


class TeamUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    leadMemberId: str | None = None
    status: str = Field(default="ACTIVE")

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in TEAM_STATUSES:
            raise ValueError("Invalid team status")
        return normalized


class TeamMemberAssignRequest(BaseModel):
    memberId: str
    role: str | None = Field(default=None, max_length=120)


class LookupOption(BaseModel):
    id: str
    label: str
    email: str | None = None


class DepartmentProjectSummary(BaseModel):
    id: str
    name: str
    status: str
    billable: bool
    memberCount: int


class TeamMemberSummary(BaseModel):
    id: str
    memberId: str
    name: str | None
    email: str | None
    role: str | None


class TeamSummary(BaseModel):
    id: str
    departmentId: str
    name: str
    description: str | None
    leadMemberId: str | None
    leadMemberName: str | None
    status: str
    memberCount: int
    projectCount: int
    members: list[TeamMemberSummary]
    projects: list[DepartmentProjectSummary]
    createdAt: datetime
    updatedAt: datetime


class DepartmentSummary(BaseModel):
    id: str
    name: str
    parentDepartmentId: str | None
    headMemberId: str | None
    headMemberName: str | None
    status: str
    teamCount: int
    memberCount: int
    projectCount: int
    teams: list[TeamSummary]
    createdAt: datetime
    updatedAt: datetime


class DepartmentListResponse(BaseModel):
    items: list[DepartmentSummary]
    total: int


class DepartmentMetaResponse(BaseModel):
    members: list[LookupOption]
    departments: list[LookupOption]
