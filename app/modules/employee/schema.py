"""
Employee module — Pydantic schemas for request/response DTOs.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── Nested response models ────────────────────────────────────────────────────


class AttendanceTodayResponse(BaseModel):
    """Today's attendance status for an employee."""

    status: str  # PRESENT | ABSENT | WORK_FROM_HOME | HALF_DAY | NO_RECORD
    clock_in: Optional[str] = None
    clock_out: Optional[str] = None

    model_config = {"from_attributes": True}


class RoleBriefResponse(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


# ─── Employee list item ────────────────────────────────────────────────────────


class EmployeeListItem(BaseModel):
    """
    Single row in the employee table.
    Combines Member + User + Role + today's AttendanceRecord.
    """

    member_id: str
    user_id: str
    name: str
    email: str
    image: Optional[str] = None
    user_principal_name: Optional[str] = None
    role: Optional[RoleBriefResponse] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    joined_at: str  # ISO datetime string
    attendance_today: AttendanceTodayResponse
    microsoft_synced: bool = False

    model_config = {"from_attributes": True}


# ─── Paginated list response ───────────────────────────────────────────────────


class EmployeeListResponse(BaseModel):
    items: list[EmployeeListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


# ─── Query filters ─────────────────────────────────────────────────────────────


class EmployeeListFilters(BaseModel):
    """Query parameters for the employee list endpoint."""

    search: Optional[str] = None
    department_id: Optional[str] = None
    role_id: Optional[str] = None
    attendance_status: Optional[str] = None  # PRESENT | ABSENT | WORK_FROM_HOME | HALF_DAY
    page: int = 1
    page_size: int = 25


# ─── Employee Delete ────────────────────────────────────────────────────────────


class EmployeeDeletePreview(BaseModel):
    member_id: str
    name: str
    email: str
    interview_count: int
    team_membership_count: int


class EmployeeDeleteResponse(BaseModel):
    member_id: str
    unassigned_interviews: int
    removed_team_memberships: int


# ─── Employee Role Update ──────────────────────────────────────────


class UpdateEmployeeRoleRequest(BaseModel):
    role_id: str


class UpdateEmployeeRoleResponse(BaseModel):
    member_id: str
    name: str
    role_id: str
    role_name: str


# ─── Employee Deactivate ──────────────────────────────────────────


class EmployeeDeactivateResponse(BaseModel):
    member_id: str
    name: str
    email: str
    status: str


# ─── Employee Detail ────────────────────────────────────────────────────────────


class EmployeePersonBrief(BaseModel):
    """A lightweight reference to another person (manager / direct report)."""

    member_id: Optional[str] = None
    user_id: Optional[str] = None
    name: str
    email: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    image: Optional[str] = None
    microsoft_id: Optional[str] = None

    model_config = {"from_attributes": True}


class EmployeeGroupBrief(BaseModel):
    """A Microsoft 365 group membership summary."""

    id: str
    display_name: str
    description: Optional[str] = None
    group_type: Optional[str] = None

    model_config = {"from_attributes": True}


class EmployeeContactInfo(BaseModel):
    email: Optional[str] = None
    user_principal_name: Optional[str] = None
    mobile_phone: Optional[str] = None
    business_phones: list[str] = []
    office_location: Optional[str] = None

    model_config = {"from_attributes": True}


class EmployeeAddress(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    model_config = {"from_attributes": True}


class EmployeeEmployment(BaseModel):
    employee_id: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    company_name: Optional[str] = None
    employee_type: Optional[str] = None
    hire_date: Optional[str] = None
    usage_location: Optional[str] = None
    user_type: Optional[str] = None
    preferred_language: Optional[str] = None

    model_config = {"from_attributes": True}


class EmployeeSyncInfo(BaseModel):
    microsoft_id: Optional[str] = None
    synced_at: Optional[str] = None
    created_date_time: Optional[str] = None
    account_enabled: bool = True
    status: str = "ACTIVE"

    model_config = {"from_attributes": True}


class EmployeeDetailResponse(BaseModel):
    """Full detail view for a single employee."""

    member_id: str
    user_id: Optional[str] = None
    name: str
    given_name: Optional[str] = None
    surname: Optional[str] = None
    image: Optional[str] = None
    profile_photo_url: Optional[str] = None
    contact: EmployeeContactInfo
    address: Optional[EmployeeAddress] = None
    employment: EmployeeEmployment
    role: Optional[RoleBriefResponse] = None
    manager: Optional[EmployeePersonBrief] = None
    direct_reports: list[EmployeePersonBrief] = []
    manager_chain: list[dict[str, Any]] = []
    groups: list[EmployeeGroupBrief] = []
    sync: EmployeeSyncInfo
    attendance_today: AttendanceTodayResponse
    joined_at: str

    model_config = {"from_attributes": True}


class EmployeeRefreshResponse(BaseModel):
    member_id: str
    synced_at: str
    direct_reports_count: int
    groups_count: int
    manager_resolved: bool


class EmployeeGroupListResponse(BaseModel):
    member_id: str
    groups: list[EmployeeGroupBrief]


class EmployeeDirectReportsResponse(BaseModel):
    member_id: str
    direct_reports: list[EmployeePersonBrief]


class EmployeeManagerChainResponse(BaseModel):
    member_id: str
    manager_chain: list[dict[str, Any]]


# ─── Employee Update ───────────────────────────────────────────────────────────


class UpdateEmployeeDetailsRequest(BaseModel):
    """Editable employee fields (non-Entra overrides)."""

    display_name: Optional[str] = Field(default=None, max_length=255)
    given_name: Optional[str] = Field(default=None, max_length=255)
    surname: Optional[str] = Field(default=None, max_length=255)
    job_title: Optional[str] = Field(default=None, max_length=255)
    department_name: Optional[str] = Field(default=None, max_length=255)
    mobile_phone: Optional[str] = Field(default=None, max_length=50)
    office_location: Optional[str] = Field(default=None, max_length=255)
    employee_type: Optional[str] = Field(default=None, max_length=100)
    employee_hire_date: Optional[date] = None
    usage_location: Optional[str] = Field(default=None, max_length=10)
    company_name: Optional[str] = Field(default=None, max_length=255)
    employee_id: Optional[str] = Field(default=None, max_length=255)
    street_address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country: Optional[str] = Field(default=None, max_length=100)


class UpdateEmployeeDetailsResponse(BaseModel):
    member_id: str
    name: str
    employment: EmployeeEmployment
    contact: EmployeeContactInfo
    synced_at: Optional[str] = None
