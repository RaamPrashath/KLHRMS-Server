from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

DEPARTMENT_STATUSES = {"ACTIVE", "INACTIVE"}


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


class DepartmentMemberSummary(BaseModel):
    id: str
    memberId: str
    name: str | None
    email: str | None


class DepartmentHeadSummary(BaseModel):
    id: str
    memberId: str
    name: str | None
    email: str | None
    assignedAt: datetime


class DepartmentSummary(BaseModel):
    id: str
    name: str
    parentDepartmentId: str | None
    headMemberId: str | None
    headMemberName: str | None
    status: str
    memberCount: int
    projectCount: int
    members: list[DepartmentMemberSummary]
    heads: list[DepartmentHeadSummary]
    projects: list[DepartmentProjectSummary]
    createdAt: datetime
    updatedAt: datetime


class DepartmentListResponse(BaseModel):
    items: list[DepartmentSummary]
    total: int


class DepartmentMetaResponse(BaseModel):
    members: list[LookupOption]
    departments: list[LookupOption]


class BulkMembersRequest(BaseModel):
    memberIds: list[str]


class HeadAssignRequest(BaseModel):
    headMemberId: str
