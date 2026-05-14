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
AttendanceWorkLocation = Literal["OFFICE", "REMOTE"]

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
    work_location: AttendanceWorkLocation = Field(
        ...,
        description="Declared work location for this clock-in.",
    )
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0)
    project_id: str | None = Field(default=None, max_length=36)
    project_task_id: str | None = Field(default=None, max_length=36)
    description: str | None = Field(default=None, max_length=1000)


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
    employee_name: str | None = Field(
        default=None,
        description="Partial name search against user.name. Only valid for organization-scope callers.",
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
    employee_name is populated for org-scope list queries (joined from Member → User).
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
    # Populated for org-scope list queries; null for self-scope responses.
    employee_name: str | None = Field(default=None, alias="employeeName")

    model_config = {"from_attributes": True, "populate_by_name": True}


class AttendanceListResponse(BaseModel):
    """Paginated list of attendance records."""

    items: list[AttendanceRecordResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Bulk work-log schemas
# ---------------------------------------------------------------------------


class BulkWorkLogItem(BaseModel):
    """
    A single work block within a day.

    startTime and endTime must be timezone-aware datetimes.
    Both must fall on the same calendar date.
    startTime must be strictly before endTime.
    """

    startTime: dt.datetime = Field(
        ...,
        description="Start of the work block (timezone-aware).",
    )
    endTime: dt.datetime = Field(
        ...,
        description="End of the work block (timezone-aware).",
    )
    projectId: str | None = Field(default=None, max_length=36)
    projectTaskId: str | None = Field(default=None, max_length=36)
    title: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_time_order(self) -> "BulkWorkLogItem":
        if self.startTime >= self.endTime:
            raise ValueError("startTime must be before endTime")
        return self


class BulkDayPayload(BaseModel):
    """
    One day's worth of work logs.

    date:  the calendar date these logs belong to.
    logs:  list of work blocks — may be empty (signals deletion of that day).
    """

    date: dt.date = Field(..., description="Calendar date for this day's logs.")
    logs: list[BulkWorkLogItem] = Field(
        default_factory=list,
        description="Work blocks for this day. Empty list deletes the day.",
    )


class BulkUpsertRequest(BaseModel):
    """
    Bulk upsert request body.

    days: one or more day payloads to save.
    employee_id: optional — for future broader-scope flows.
                 Omit for self-service (defaults to the calling member).
    """

    days: list[BulkDayPayload] = Field(..., min_length=1)
    employee_id: str | None = Field(
        default=None,
        description=_MEMBER_ID_DESC + " Omit to default to self.",
    )


class BulkRangeQuery(BaseModel):
    """Query parameters for the bulk range fetch endpoint."""

    date_from: dt.date = Field(..., alias="from", description="Inclusive start date.")
    date_to: dt.date = Field(..., alias="to", description="Inclusive end date.")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_range(self) -> "BulkRangeQuery":
        if self.date_to < self.date_from:
            raise ValueError("'to' must be >= 'from'")
        return self


class BulkDayQuery(BaseModel):
    """Query parameters for the single-day fetch endpoint."""

    date: dt.date = Field(..., description="Calendar date to fetch.")


class BulkDeleteDayRequest(BaseModel):
    """Request body for deleting one day's bulk attendance entry."""

    date: dt.date = Field(..., description="Calendar date to delete.")


# ---------------------------------------------------------------------------
# Bulk work-log response schemas
# ---------------------------------------------------------------------------


class WorkLogResponse(BaseModel):
    """Response DTO for a single AttendanceWorkLog row."""

    id: str
    startTime: dt.datetime | None
    endTime: dt.datetime | None
    projectId: str | None
    projectTaskId: str | None
    title: str | None
    notes: str | None

    model_config = {"from_attributes": True}


class BulkDayResponse(BaseModel):
    """
    Response DTO for one attendance day with its child work logs.

    Mirrors the shape the Next.js calendar frontend expects.
    """

    date: dt.date
    attendanceRecordId: str
    clockIn: dt.datetime | None
    clockOut: dt.datetime | None
    totalHours: float | None
    overtimeHours: float | None
    status: str
    logs: list[WorkLogResponse]

    model_config = {"from_attributes": True}


class BulkUpsertResponse(BaseModel):
    """Response for POST /attendance/bulk-work-logs."""

    days: list[BulkDayResponse]


class BulkRangeResponse(BaseModel):
    """Response for GET /attendance/bulk-work-logs."""

    days: list[BulkDayResponse]


class BulkDaySingleResponse(BaseModel):
    """Response for GET /attendance/bulk-work-logs/day."""

    day: BulkDayResponse | None


class BulkDeleteDayResponse(BaseModel):
    """Response for DELETE /attendance/bulk-work-logs/day."""

    success: bool
    date: dt.date
