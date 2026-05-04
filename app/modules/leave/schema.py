"""Leave management request/response schemas."""
import uuid
from datetime import date, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.utils.enums import LeaveStatus


# ── Leave Type Schemas ───────────────────────────────────────────────────────

class LeaveTypeConfigCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    quota: float = Field(gt=0)
    carry_forward: bool = False
    is_paid: bool = True
    color: str = Field(default="#3b82f6", pattern=r"^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = None


class LeaveTypeConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    quota: Optional[float] = Field(None, gt=0)
    carry_forward: Optional[bool] = None
    is_paid: Optional[bool] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None
    description: Optional[str] = None


class LeaveTypeConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    quota: float
    carry_forward: bool
    is_paid: bool
    color: str
    is_active: bool
    description: Optional[str]
    created_at: Optional[date] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def coerce_to_date(cls, v):
        if isinstance(v, datetime):
            return v.date()
        return v


# ── Leave Request Schemas ──────────────────────────────────────────────────────

class LeaveRequestCreate(BaseModel):
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    reason: Optional[str] = Field(None, max_length=1000)

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, end_date: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date and end_date < start_date:
            raise ValueError("End date must be on or after start date")
        return end_date


class LeaveRequestApprove(BaseModel):
    """
    Body for approving a leave request.

    All fields are optional — an empty body {} is valid.
    The comment is stored as the approver's note visible to the employee.
    """

    model_config = ConfigDict(extra="forbid")

    comment: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional note from the approver visible to the employee.",
    )


class LeaveRequestReject(BaseModel):
    """
    Body for rejecting a leave request.

    comment is required — employees must be told why their request was rejected.
    """

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(
        min_length=1,
        max_length=1000,
        description="Reason for rejection. Required so the employee understands the decision.",
    )


class LeaveRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: str
    employee_name: Optional[str] = None
    employee_email: Optional[str] = None
    leave_type_id: str
    leave_type_name: Optional[str] = None
    leave_type_color: Optional[str] = None
    start_date: date
    end_date: date
    days: float
    reason: Optional[str]
    status: LeaveStatus
    approved_by_id: Optional[str] = None
    approver_name: Optional[str] = None
    approver_comment: Optional[str] = None
    created_at: Optional[date] = None

    @field_validator("created_at", mode="before")
    @classmethod
    def coerce_to_date(cls, v):
        if isinstance(v, datetime):
            return v.date()
        return v


# ── Leave Balance Schemas ─────────────────────────────────────────────────────

class LeaveBalanceAllocate(BaseModel):
    employee_id: str
    leave_type_id: uuid.UUID
    year: int = Field(ge=2000, le=2100)
    allocated: float = Field(gt=0)


class LeaveBalanceAutoAllocate(BaseModel):
    year: int = Field(ge=2000, le=2100)


class LeaveBalanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: str
    employee_name: Optional[str] = None
    leave_type_id: str
    leave_type_name: Optional[str] = None
    leave_type_color: Optional[str] = None
    year: int
    allocated: float
    used: float
    remaining: float
    carried_forward: float = 0
    lapsed: float = 0


# ── Holiday Schemas ──────────────────────────────────────────────────────────

class HolidayCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    holiday_date: date
    is_recurring: bool = False
    description: Optional[str] = None


class HolidayUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    holiday_date: Optional[date] = None
    is_recurring: Optional[bool] = None
    description: Optional[str] = None


class HolidayRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    holiday_date: date
    is_recurring: bool
    description: Optional[str]


# ── Calendar Schemas ───────────────────────────────────────────────────────────

class CalendarEvent(BaseModel):
    """Leave event for calendar visualization"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: str
    employee_name: Optional[str] = None
    leave_type_id: str
    leave_type_name: Optional[str] = None
    leave_type_color: Optional[str] = None
    start_date: date
    end_date: date
    days: float
    status: LeaveStatus


# ── Summary Schemas ──────────────────────────────────────────────────────────

class LeaveSummary(BaseModel):
    """Summary of leave statistics for dashboard"""
    total_requests: int
    pending_requests: int
    approved_requests: int
    rejected_requests: int
    total_days_taken: float
    by_type: Dict[str, float]