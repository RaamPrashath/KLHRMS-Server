"""
Pydantic schemas for the Attendance module.

Note on naming:
  AttendanceRecord.employeeId is treated as memberId in this codebase.
  All request/response fields that refer to the attendance owner use
  'employee_id' to match the database column name, but callers should
  understand this maps to Member.id.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AttendanceStatus = Literal["PRESENT", "HALF_DAY", "ABSENT"]

_MEMBER_ID_DESC = "Member.id of the attendance owner."


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ClockInRequest(BaseModel):
    """
    Clock-in request.

    target_member_id: optional — if omitted the actor clocks in for themselves.
    clock_in:         optional — if omitted the server uses utcnow().
    """

    target_member_id: str | None = Field(
        default=None,
        description=_MEMBER_ID_DESC + " Defaults to the actor.",
    )
    clock_in: dt.datetime | None = Field(
        default=None,
        description="Explicit clock-in timestamp (UTC). Defaults to now.",
    )


class ClockOutRequest(BaseModel):
    """
    Clock-out request.

    target_member_id: optional — if omitted the actor clocks out for themselves.
    clock_out:        optional — if omitted the server uses utcnow().
    """

    target_member_id: str | None = Field(
        default=None,
        description=_MEMBER_ID_DESC + " Defaults to the actor.",
    )
    clock_out: dt.datetime | None = Field(
        default=None,
        description="Explicit clock-out timestamp (UTC). Defaults to now.",
    )


class ManualDayEntryRequest(BaseModel):
    """
    Manual upsert of a single attendance day.

    Overwrites any existing clock or manual data for the target member/date.
    Requires attendance.edit permission.
    """

    target_member_id: str = Field(..., description=_MEMBER_ID_DESC)
    entry_date: dt.date = Field(
        ..., alias="date", description="Calendar date for the attendance row."
    )
    clock_in: dt.datetime | None = Field(default=None)
    clock_out: dt.datetime | None = Field(default=None)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_clock_order(self) -> "ManualDayEntryRequest":
        if self.clock_in is not None and self.clock_out is not None:
            if self.clock_out <= self.clock_in:
                raise ValueError("clock_out must be after clock_in")
        return self


class DeleteDayEntryRequest(BaseModel):
    """Delete a specific member/date attendance row."""

    target_member_id: str = Field(..., description=_MEMBER_ID_DESC)
    entry_date: dt.date = Field(
        ..., alias="date", description="Calendar date of the row to delete."
    )

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Filter / query schemas
# ---------------------------------------------------------------------------


class AttendanceListFilters(BaseModel):
    """Query parameters for listing attendance records."""

    target_member_id: str | None = Field(
        default=None,
        description=_MEMBER_ID_DESC + " Only valid for organization-scope callers.",
    )
    date_from: dt.date | None = Field(default=None, description="Inclusive start date.")
    date_to: dt.date | None = Field(default=None, description="Inclusive end date.")
    status: AttendanceStatus | None = Field(default=None)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    @model_validator(mode="after")
    def validate_date_range(self) -> "AttendanceListFilters":
        if self.date_from is not None and self.date_to is not None:
            if self.date_to < self.date_from:
                raise ValueError("date_to must be >= date_from")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AttendanceRecordResponse(BaseModel):
    """
    Response DTO for a single AttendanceRecord row.

    employee_id maps to AttendanceRecord.employeeId which is Member.id.
    """

    id: str
    employee_id: str = Field(alias="employeeId")
    organization_id: str = Field(alias="organizationId")
    record_date: dt.date = Field(alias="date")
    clock_in: dt.datetime | None = Field(alias="clockIn")
    clock_out: dt.datetime | None = Field(alias="clockOut")
    total_hours: float | None = Field(alias="totalHours")
    overtime_hours: float | None = Field(alias="overtimeHours")
    status: str
    entered_by_manager_id: str | None = Field(alias="enteredByManagerId")
    created_at: dt.datetime = Field(alias="createdAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class AttendanceListResponse(BaseModel):
    """Paginated list of attendance records."""

    items: list[AttendanceRecordResponse]
    total: int
    page: int
    page_size: int
