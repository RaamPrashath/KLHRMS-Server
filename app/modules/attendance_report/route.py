from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance_report.export_service import generate_attendance_report_export
from app.modules.attendance_report.schema import (
    AttendanceReportExportRequest,
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

_MIME_TYPES: dict[str, str] = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv",
}

_FILE_EXTENSIONS: dict[str, str] = {
    "xlsx": "xlsx",
    "pdf": "pdf",
    "csv": "csv",
}

AttendanceReportCtx = Annotated[
    MemberContext,
    Depends(require_permission("attendanceReport", "view")),
]


def _ensure_organization_scope(ctx: MemberContext) -> None:
    scope = getattr(ctx, "scope", None)
    if scope not in ("organization", "department"):
        raise HTTPException(
            status_code=403,
            detail="Organization or department scope is required for attendance reports",
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
    scope = getattr(ctx, "scope", None) or "self"
    _ensure_organization_scope(ctx)
    return await list_report_options(
        db,
        ctx.organization.id,
        scope=scope,
        actor_member_id=ctx.member.id,
    )


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
    department_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5000, ge=1, le=5000),
) -> AttendanceReportListResponse:
    scope = getattr(ctx, "scope", None) or "self"
    _ensure_organization_scope(ctx)
    filters = AttendanceReportFilters(
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        employee_ids=employee_ids or [],
        department_id=department_id,
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
        department_id=filters.department_id,
        page=filters.page,
        page_size=filters.page_size,
        scope=scope,
        actor_member_id=ctx.member.id,
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
                projectName=row.project_name,
                clientName=row.client_name,
                taskName=row.task_name,
                clockOutDescription=row.clock_out_description,
                leaveTypeName=row.leave_type_name,
                entryType=row.entry_type,
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


@router.post(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export selected attendance report rows",
)
async def export_attendance_report(
    body: AttendanceReportExportRequest,
    ctx: AttendanceReportCtx,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    scope = getattr(ctx, "scope", None) or "self"
    _ensure_organization_scope(ctx)

    db_rows = None
    if body.format == "xlsx" and body.mode == "timesheet":
        import calendar
        # We need to fetch rows from the database for the entire range of months.
        # Let's extract the date range.
        dates = body.dateColumns or [row.date for row in body.rows]
        latest_date = max(dates) if dates else (body.dateTo or date.today())
        
        # From January 1st of that year to the end of the latest month
        _, last_day = calendar.monthrange(latest_date.year, latest_date.month)
        date_from = date(latest_date.year, 1, 1)
        date_to = date(latest_date.year, latest_date.month, last_day)
        
        # Fetch the records for this range
        employee_ids = [emp.id for emp in body.employees]
        
        rows_data, _, _ = await list_attendance_report(
            db=db,
            organization_id=ctx.organization.id,
            date_from=date_from,
            date_to=date_to,
            project_id=body.projectId,
            employee_ids=employee_ids,
            page=1,
            page_size=100000,
            scope=scope,
            actor_member_id=ctx.member.id,
        )
        
        db_rows = [
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
                projectName=row.project_name,
                clientName=row.client_name,
                taskName=row.task_name,
                clockOutDescription=row.clock_out_description,
                leaveTypeName=row.leave_type_name,
                entryType=row.entry_type,
            )
            for row in rows_data
        ]

    content = generate_attendance_report_export(body, db_rows=db_rows)
    import io

    filename = f"attendance-report.{_FILE_EXTENSIONS[body.format]}"
    return StreamingResponse(
        io.BytesIO(content),
        media_type=_MIME_TYPES[body.format],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )
