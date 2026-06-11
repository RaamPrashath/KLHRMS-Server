from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AttendanceReportEmployeeOption(BaseModel):
    id: str
    name: str
    email: str | None = None


class AttendanceReportProjectOption(BaseModel):
    id: str
    name: str
    members: list[AttendanceReportEmployeeOption]


class AttendanceReportOptionsResponse(BaseModel):
    employees: list[AttendanceReportEmployeeOption]
    projects: list[AttendanceReportProjectOption]


class AttendanceReportFilters(BaseModel):
    date_from: date
    date_to: date
    project_id: str | None = Field(default=None, max_length=36)
    employee_ids: list[str] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=5000, ge=1, le=5000)

    @model_validator(mode="after")
    def validate_date_range(self) -> "AttendanceReportFilters":
        if self.date_to < self.date_from:
            raise ValueError("date_to must be >= date_from")
        return self


class AttendanceReportRow(BaseModel):
    attendanceRecordId: str
    employeeId: str
    employeeName: str
    employeeEmail: str | None = None
    date: date
    clockIn: datetime | None = None
    clockOut: datetime | None = None
    totalHours: float | None = None
    departmentName: str | None = None
    projectName: str | None = None
    clientName: str | None = None
    taskName: str | None = None
    clockOutDescription: str | None = None
    leaveTypeName: str | None = None
    entryType: str | None = None


class AttendanceReportSummary(BaseModel):
    total_days: int
    total_hours: float
    employee_count: int


class AttendanceReportListResponse(BaseModel):
    items: list[AttendanceReportRow]
    total: int
    page: int
    page_size: int
    summary: AttendanceReportSummary


AttendanceReportExportFormat = Literal["xlsx", "pdf", "csv"]
AttendanceReportExportMode = Literal["report", "timesheet"]


class AttendanceReportExportEmployee(BaseModel):
    id: str
    name: str
    email: str | None = None


class AttendanceReportExportRequest(BaseModel):
    format: AttendanceReportExportFormat
    mode: AttendanceReportExportMode
    title: str = Field(default="Attendance Report", max_length=160)
    periodLabel: str = Field(default="", max_length=160)
    dateColumns: list[date] = Field(default_factory=list)
    employees: list[AttendanceReportExportEmployee] = Field(default_factory=list)
    rows: list[AttendanceReportRow] = Field(default_factory=list)
    force8: bool = False
    projectId: str | None = Field(default=None, max_length=36)
    dateFrom: date | None = Field(default=None)
    dateTo: date | None = Field(default=None)

