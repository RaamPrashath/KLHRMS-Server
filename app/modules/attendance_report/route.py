from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance_report.schema import (
    AttendanceReportFilters,
    AttendanceReportListResponse,
    AttendanceReportOptionsResponse,
    AttendanceReportRow,
    AttendanceReportSummary,
)
from app.modules.attendance_report.service import list_attendance_report, list_report_options
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/attendance-report", tags=["attendance-report"])

AttendanceReportCtx = Annotated[
    MemberContext,
    Depends(require_permission("attendanceReport", "view")),
]


def _ensure_organization_scope(ctx: MemberContext) -> None:
    if getattr(ctx, "scope", None) != "organization":
        raise HTTPException(
            status_code=403,
            detail="Organization scope is required for attendance reports",
        )


@router.get(
    "/options",
    response_model=AttendanceReportOptionsResponse,
    status_code=status.HTTP_200_OK,
    summary="List attendance report filter options",
)
async def get_attendance_report_options(
    ctx: AttendanceReportCtx,
    db: AsyncSession = Depends(get_db),
) -> AttendanceReportOptionsResponse:
    _ensure_organization_scope(ctx)
    return await list_report_options(db, ctx.organization.id)


@router.get(
    "",
    response_model=AttendanceReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List attendance report rows",
)
async def get_attendance_report(
    ctx: AttendanceReportCtx,
    db: AsyncSession = Depends(get_db),
    date_from: date = Query(...),
    date_to: date = Query(...),
    project_id: str | None = Query(default=None),
    employee_ids: Annotated[list[str] | None, Query(alias="employee_id")] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5000, ge=1, le=5000),
) -> AttendanceReportListResponse:
    _ensure_organization_scope(ctx)
    filters = AttendanceReportFilters(
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        employee_ids=employee_ids or [],
        page=page,
        page_size=page_size,
    )
    rows, total, summary = await list_attendance_report(
        db,
        ctx.organization.id,
        date_from=filters.date_from,
        date_to=filters.date_to,
        project_id=filters.project_id,
        employee_ids=filters.employee_ids,
        page=filters.page,
        page_size=filters.page_size,
    )
    return AttendanceReportListResponse(
        items=[
            AttendanceReportRow(
                attendanceRecordId=row.attendance_record_id,
                employeeId=row.employee_id,
                employeeName=row.employee_name,
                employeeEmail=row.employee_email,
                date=row.day,
                clockIn=row.clock_in,
                clockOut=row.clock_out,
                totalHours=row.total_hours,
                departmentName=row.department_name,
                teamName=row.team_name,
                projectName=row.project_name,
                taskName=row.task_name,
                clockOutDescription=row.clock_out_description,
            )
            for row in rows
        ],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        summary=AttendanceReportSummary(
            total_days=summary.total_days,
            total_hours=summary.total_hours,
            employee_count=summary.employee_count,
        ),
    )
