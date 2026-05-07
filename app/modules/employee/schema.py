"""
Employee module — Pydantic schemas for request/response DTOs.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


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
    role: Optional[RoleBriefResponse] = None
    joined_at: str  # ISO datetime string
    attendance_today: AttendanceTodayResponse

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
