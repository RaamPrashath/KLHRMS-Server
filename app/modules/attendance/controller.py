"""
Attendance controller — thin orchestration layer.

Accepts validated schema inputs and resolved AttendanceAccessContext,
calls service functions, and returns response DTOs.
All HTTPException translation happens in the service layer; the controller
only maps ORM objects to response schemas.
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.schema import (
    AttendanceListFilters,
    AttendanceListResponse,
    AttendanceRecordResponse,
    ClockInRequest,
    ClockOutRequest,
    DeleteDayEntryRequest,
    ManualDayEntryRequest,
    WorkLogReportDetailResponse,
    WorkLogReportFilters,
    WorkLogReportListResponse,
    WorkLogReportRow,
    WorkLogReportSummary,
)
from app.modules.attendance import service
from app.shared.deps.attendance_permissions import AttendanceAccessContext
from app.shared.config import get_settings


def _to_response(record: object, employee_name: str | None = None) -> AttendanceRecordResponse:
    resp = AttendanceRecordResponse.model_validate(record)
    if employee_name is not None:
        resp.employee_name = employee_name
    return resp


# ---------------------------------------------------------------------------
# Clock-in
# ---------------------------------------------------------------------------


async def handle_clock_in(
    access: AttendanceAccessContext,
    db: AsyncSession,
    body: ClockInRequest,
) -> AttendanceRecordResponse:
    target_id = body.target_member_id or access.member.id

    # Validate target member belongs to the organization (unless self).
    if target_id != access.member.id:
        await service.resolve_target_member(db, access.organization.id, target_id)

    record = await service.clock_in(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=target_id,
        scope=access.permission_scope,
        clock_in_time=body.clock_in,
        work_location=body.work_location,
        latitude=body.latitude,
        longitude=body.longitude,
        accuracy_meters=body.accuracy_meters,
        project_id=body.project_id,
        project_task_id=body.project_task_id,
        description=body.description,
        office_latitude=access.organization.latitude,
        office_longitude=access.organization.longitude,
        office_radius_meters=get_settings().attendance_office_radius_meters,
    )
    return _to_response(record)


# ---------------------------------------------------------------------------
# Clock-out
# ---------------------------------------------------------------------------


async def handle_clock_out(
    access: AttendanceAccessContext,
    db: AsyncSession,
    body: ClockOutRequest,
) -> list[AttendanceRecordResponse]:
    target_id = body.target_member_id or access.member.id

    if target_id != access.member.id:
        await service.resolve_target_member(db, access.organization.id, target_id)

    policy = await service.load_policy(db, access.organization.id)

    records = await service.clock_out(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=target_id,
        scope=access.permission_scope,
        policy=policy,
        clock_out_time=body.clock_out,
        work_log_text=body.work_log_text,
    )
    return [_to_response(r) for r in records]


# ---------------------------------------------------------------------------
# Manual day upsert
# ---------------------------------------------------------------------------


async def handle_upsert_manual_day(
    access: AttendanceAccessContext,
    db: AsyncSession,
    body: ManualDayEntryRequest,
) -> AttendanceRecordResponse:
    await service.resolve_target_member(db, access.organization.id, body.target_member_id)

    policy = await service.load_policy(db, access.organization.id)

    record = await service.upsert_manual_day(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=body.target_member_id,
        scope=access.permission_scope,
        policy=policy,
        day=body.entry_date,
        clock_in_time=body.clock_in,
        clock_out_time=body.clock_out,
        entry_type=body.entry_type,
    )
    return _to_response(record)


# ---------------------------------------------------------------------------
# Delete day entry
# ---------------------------------------------------------------------------


async def handle_delete_day_entry(
    access: AttendanceAccessContext,
    db: AsyncSession,
    body: DeleteDayEntryRequest,
) -> None:
    await service.resolve_target_member(db, access.organization.id, body.target_member_id)

    await service.delete_day_entry(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=body.target_member_id,
        scope=access.permission_scope,
        day=body.entry_date,
    )


# ---------------------------------------------------------------------------
# Get my attendance
# ---------------------------------------------------------------------------


async def handle_get_my_attendance(
    access: AttendanceAccessContext,
    db: AsyncSession,
    filters: AttendanceListFilters,
) -> AttendanceListResponse:
    rows, total = await service.get_my_attendance(
        db=db,
        organization_id=access.organization.id,
        member_id=access.member.id,
        date_from=filters.date_from,
        date_to=filters.date_to,
        status_filter=filters.status,
        page=filters.page,
        page_size=filters.page_size,
    )
    return AttendanceListResponse(
        items=[_to_response(record, name) for record, name in rows],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


# ---------------------------------------------------------------------------
# List attendance
# ---------------------------------------------------------------------------


async def handle_list_attendance(
    access: AttendanceAccessContext,
    db: AsyncSession,
    filters: AttendanceListFilters,
) -> AttendanceListResponse:
    rows, total = await service.list_attendance(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        scope=access.permission_scope,
        target_member_id=filters.target_member_id,
        employee_name=filters.employee_name,
        date_from=filters.date_from,
        date_to=filters.date_to,
        status_filter=filters.status,
        page=filters.page,
        page_size=filters.page_size,
    )
    return AttendanceListResponse(
        items=[_to_response(record, name) for record, name in rows],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


# ---------------------------------------------------------------------------
# Get attendance day
# ---------------------------------------------------------------------------


async def handle_get_attendance_day(
    access: AttendanceAccessContext,
    db: AsyncSession,
    target_member_id: str,
    day: dt.date,
) -> AttendanceRecordResponse:
    await service.resolve_target_member(db, access.organization.id, target_member_id)

    record = await service.get_attendance_day(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=target_member_id,
        scope=access.permission_scope,
        day=day,
    )
    return _to_response(record)


# ---------------------------------------------------------------------------
# Bulk work-log handlers
# ---------------------------------------------------------------------------


async def handle_upsert_bulk_work_logs(
    access: AttendanceAccessContext,
    db: AsyncSession,
    body: object,  # BulkUpsertRequest — imported at call site to avoid circular
) -> object:  # BulkUpsertResponse
    from app.modules.attendance.schema import (
        BulkDayResponse,
        BulkUpsertResponse,
        WorkLogResponse,
    )

    # Resolve target: default to self.
    target_id: str = body.employee_id or access.member.id  # type: ignore[union-attr]

    # For non-self targets, verify the member exists in the org.
    if target_id != access.member.id:
        await service.resolve_target_member(db, access.organization.id, target_id)

    policy = await service.load_policy(db, access.organization.id)

    results = await service.upsert_bulk_work_logs(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=target_id,
        scope=access.permission_scope,
        policy=policy,
        days=body.days,  # type: ignore[union-attr]
    )

    day_responses: list[BulkDayResponse] = []
    for result in results:
        day_responses.append(
            BulkDayResponse(
                date=result.record.date,
                attendanceRecordId=result.record.id,
                clockIn=result.record.clockIn,
                clockOut=result.record.clockOut,
                totalHours=result.record.totalHours,
                overtimeHours=result.record.overtimeHours,
                status=result.record.status,
                logs=[
                    WorkLogResponse(
                        id=log.id,
                        startTime=log.startTime,
                        endTime=log.endTime,
                        projectId=log.projectId,
                        projectTaskId=log.projectTaskId,
                        title=log.title,
                        notes=log.notes,
                    )
                    for log in result.logs
                ],
            )
        )

    return BulkUpsertResponse(days=day_responses)


async def handle_get_bulk_work_logs_range(
    access: AttendanceAccessContext,
    db: AsyncSession,
    date_from: dt.date,
    date_to: dt.date,
) -> object:  # BulkRangeResponse
    from app.modules.attendance.schema import (
        BulkDayResponse,
        BulkRangeResponse,
        WorkLogResponse,
    )

    results = await service.get_bulk_work_logs_range(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=access.member.id,
        scope=access.permission_scope,
        date_from=date_from,
        date_to=date_to,
    )

    day_responses: list[BulkDayResponse] = [
        BulkDayResponse(
            date=result.record.date,
            attendanceRecordId=result.record.id,
            clockIn=result.record.clockIn,
            clockOut=result.record.clockOut,
            totalHours=result.record.totalHours,
            overtimeHours=result.record.overtimeHours,
            status=result.record.status,
            logs=[
                WorkLogResponse(
                    id=log.id,
                    startTime=log.startTime,
                    endTime=log.endTime,
                    projectId=log.projectId,
                    projectTaskId=log.projectTaskId,
                    title=log.title,
                    notes=log.notes,
                )
                for log in result.logs
            ],
        )
        for result in results
    ]

    return BulkRangeResponse(days=day_responses)


async def handle_get_bulk_work_logs_day(
    access: AttendanceAccessContext,
    db: AsyncSession,
    day: dt.date,
) -> object:  # BulkDaySingleResponse
    from app.modules.attendance.schema import (
        BulkDayResponse,
        BulkDaySingleResponse,
        WorkLogResponse,
    )

    result = await service.get_bulk_work_logs_day(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=access.member.id,
        scope=access.permission_scope,
        day=day,
    )

    if result is None:
        return BulkDaySingleResponse(day=None)

    return BulkDaySingleResponse(
        day=BulkDayResponse(
            date=result.record.date,
            attendanceRecordId=result.record.id,
            clockIn=result.record.clockIn,
            clockOut=result.record.clockOut,
            totalHours=result.record.totalHours,
            overtimeHours=result.record.overtimeHours,
            status=result.record.status,
            logs=[
                WorkLogResponse(
                    id=log.id,
                    startTime=log.startTime,
                    endTime=log.endTime,
                    projectId=log.projectId,
                    projectTaskId=log.projectTaskId,
                    title=log.title,
                    notes=log.notes,
                )
                for log in result.logs
            ],
        )
    )


async def handle_delete_bulk_work_logs_day(
    access: AttendanceAccessContext,
    db: AsyncSession,
    day: dt.date,
) -> object:  # BulkDeleteDayResponse
    from app.modules.attendance.schema import BulkDeleteDayResponse

    await service.delete_bulk_work_logs_day(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=access.member.id,
        scope=access.permission_scope,
        day=day,
    )

    return BulkDeleteDayResponse(success=True, date=day)


def _ensure_org_scope(access: AttendanceAccessContext) -> None:
    from fastapi import HTTPException

    if access.permission_scope != "organization":
        raise HTTPException(
            status_code=403,
            detail="Organization scope is required for work-log reporting",
        )


async def handle_list_work_log_reports(
    access: AttendanceAccessContext,
    db: AsyncSession,
    filters: WorkLogReportFilters,
) -> WorkLogReportListResponse:
    _ensure_org_scope(access)
    rows, total, summary = await service.list_work_log_reports(
        db=db,
        organization_id=access.organization.id,
        date_from=filters.date_from,
        date_to=filters.date_to,
        department_id=filters.department_id,
        employee_id=filters.employee_id,
        employee_name=filters.employee_name,
        page=filters.page,
        page_size=filters.page_size,
    )
    items = [
        WorkLogReportRow(
            attendanceRecordId=row.attendance_record_id,
            employeeId=row.employee_id,
            employeeName=row.employee_name,
            date=row.day,
            clockIn=row.clock_in,
            clockOut=row.clock_out,
            totalHours=row.total_hours,
            departmentName=row.department_name,
            projectName=row.project_name,
            taskName=row.task_name,
            dailyWorkLogPreview=service._work_log_preview(row.daily_work_log),
            hasFullLog=bool(
                row.daily_work_log
                and service._work_log_preview(row.daily_work_log) != row.daily_work_log
            ),
        )
        for row in rows
    ]
    return WorkLogReportListResponse(
        items=items,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        summary=WorkLogReportSummary(
            total_days=summary.total_days,
            total_hours=summary.total_hours,
            employee_count=summary.employee_count,
        ),
    )


async def handle_get_work_log_report_detail(
    access: AttendanceAccessContext,
    db: AsyncSession,
    attendance_record_id: str,
) -> WorkLogReportDetailResponse:
    from fastapi import HTTPException

    _ensure_org_scope(access)
    row = await service.get_work_log_report_detail(
        db=db,
        organization_id=access.organization.id,
        attendance_record_id=attendance_record_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Work-log report entry not found")

    return WorkLogReportDetailResponse(
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
        taskName=row.task_name,
        dailyWorkLog=row.daily_work_log,
    )


async def handle_export_work_log_reports(
    access: AttendanceAccessContext,
    db: AsyncSession,
    filters: WorkLogReportFilters,
) -> list[service.WorkLogReportRowData]:
    _ensure_org_scope(access)
    return await service.export_work_log_reports(
        db=db,
        organization_id=access.organization.id,
        date_from=filters.date_from,
        date_to=filters.date_to,
        department_id=filters.department_id,
        employee_id=filters.employee_id,
        employee_name=filters.employee_name,
    )
