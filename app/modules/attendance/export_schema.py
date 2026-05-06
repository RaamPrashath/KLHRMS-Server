"""
Pydantic schemas for the attendance export endpoint.

The frontend sends the currently visible rows directly — no re-query needed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AttendanceExportStatus = Literal["PRESENT", "HALF_DAY", "ABSENT"]
ExportFormat = Literal["xlsx", "pdf", "csv"]


class AttendanceExportRow(BaseModel):
    """A single attendance record row as sent by the frontend (list mode)."""

    id: str
    date: str = Field(..., description="ISO date YYYY-MM-DD")
    clockIn: str | None = None
    clockOut: str | None = None
    totalHours: float | None = None
    status: str
    employeeName: str | None = None


# ─── Pivot export schemas ─────────────────────────────────────────────────────


class PivotCell(BaseModel):
    """One day's data for a single employee in the pivot table."""

    date: str                   # YYYY-MM-DD
    totalHours: float | None = None
    status: str | None = None   # PRESENT | HALF_DAY | ABSENT | None (no record)


class PivotEmployeeRow(BaseModel):
    """One employee row in the pivot table."""

    employeeName: str
    cells: list[PivotCell]      # ordered by date ascending
    total: float                # sum of totalHours across the period


class AttendancePivotExportPayload(BaseModel):
    """Pivot-shaped export payload sent by the frontend."""

    dateColumns: list[str]          # ordered YYYY-MM-DD strings (the column headers)
    rows: list[PivotEmployeeRow]
    periodLabel: str                # e.g. "May 4 – May 10, 2026"


# ─── Unified request ──────────────────────────────────────────────────────────


class AttendanceExportRequest(BaseModel):
    """Request body for the export endpoint."""

    format: ExportFormat
    exportMode: Literal["list", "pivot"] = "list"

    # list mode
    records: list[AttendanceExportRow] = Field(default_factory=list)
    showEmployeeColumn: bool = False
    title: str = Field(default="Attendance Report", max_length=120)

    # pivot mode
    pivotData: AttendancePivotExportPayload | None = None
