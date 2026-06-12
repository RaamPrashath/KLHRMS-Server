from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_work_log import AttendanceWorkLog
from app.models.department import Department
from app.models.department_member import DepartmentMember
from app.models.leave import LeaveRequest, LeaveType
from app.models.member import Member
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.project_task import ProjectTask
from app.models.user import User
from app.modules.attendance_report.schema import (
    AttendanceReportEmployeeOption,
    AttendanceReportOptionsResponse,
    AttendanceReportProjectOption,
)


@dataclass(frozen=True)
class AttendanceReportSummaryData:
    total_days: int
    total_hours: float
    employee_count: int


@dataclass(frozen=True)
class AttendanceReportRowData:
    attendance_record_id: str
    employee_id: str
    employee_name: str
    employee_email: str | None
    day: date
    clock_in: datetime | None
    clock_out: datetime | None
    total_hours: float | None
    department_name: str | None
    project_name: str | None
    client_name: str | None
    task_name: str | None
    clock_out_description: str | None
    leave_type_name: str | None = None
    entry_type: str | None = None


def _display_employee_name(raw_name: str | None, email: str | None, fallback_id: str) -> str:
    normalized_name = (raw_name or "").strip()
    normalized_email = (email or "").strip()
    if normalized_name and normalized_name.lower() != normalized_email.lower():
        return normalized_name
    if normalized_email:
        local = normalized_email.split("@", 1)[0].strip()
        return " ".join(part.capitalize() for part in local.replace(".", " ").replace("_", " ").split()) or normalized_email
    return fallback_id


def _clock_out_description_subquery(organization_id: str):
    return (
        select(AttendanceWorkLog.notes)
        .where(
            AttendanceWorkLog.attendanceRecordId == AttendanceRecord.id,
            AttendanceWorkLog.organizationId == organization_id,
            AttendanceWorkLog.notes.is_not(None),
            AttendanceWorkLog.notes != "",
            or_(
                AttendanceRecord.description.is_(None),
                AttendanceWorkLog.notes != AttendanceRecord.description,
            ),
        )
        .order_by(AttendanceWorkLog.endTime.desc(), AttendanceWorkLog.createdAt.desc())
        .limit(1)
        .scalar_subquery()
    )


def _department_name_subquery(organization_id: str):
    return (
        select(func.min(Department.name))
        .select_from(DepartmentMember)
        .join(Department, Department.id == DepartmentMember.departmentId)
        .where(
            DepartmentMember.memberId == AttendanceRecord.employeeId,
            Department.organizationId == organization_id,
        )
        .scalar_subquery()
    )


def _project_filter_exists(project_id: str):
    return (
        select(AttendanceWorkLog.id)
        .where(
            AttendanceWorkLog.attendanceRecordId == AttendanceRecord.id,
            AttendanceWorkLog.projectId == project_id,
        )
        .exists()
    )


def _apply_filters(
    query,
    organization_id: str,
    *,
    date_from: date,
    date_to: date,
    project_id: str | None,
    employee_ids: list[str],
):
    query = query.where(
        AttendanceRecord.organizationId == organization_id,
        AttendanceRecord.date >= date_from,
        AttendanceRecord.date <= date_to,
    )
    if project_id:
        query = query.where(
            or_(
                AttendanceRecord.projectId == project_id,
                _project_filter_exists(project_id),
            )
        )
    if employee_ids:
        query = query.where(AttendanceRecord.employeeId.in_(employee_ids))
    return query


async def list_report_options(
    db: AsyncSession,
    organization_id: str,
) -> AttendanceReportOptionsResponse:
    employee_result = await db.execute(
        select(Member.id, User.name, User.email)
        .join(User, User.id == Member.userId)
        .where(Member.organizationId == organization_id)
        .order_by(User.name.asc().nullslast(), User.email.asc())
    )
    employees = [
        AttendanceReportEmployeeOption(
            id=member_id,
            name=_display_employee_name(name, email, member_id),
            email=email,
        )
        for member_id, name, email in employee_result.all()
    ]

    project_result = await db.execute(
        select(Project)
        .where(
            Project.organizationId == organization_id,
            Project.status == "ACTIVE",
            Project.deletedAt.is_(None),
        )
        .options(joinedload(Project.members).joinedload(ProjectMember.member).joinedload(Member.user))
        .order_by(Project.name.asc())
    )
    projects = []
    for project in project_result.unique().scalars().all():
        members = sorted(
            [
                AttendanceReportEmployeeOption(
                    id=assignment.memberId,
                    name=_display_employee_name(
                        assignment.member.user.name if assignment.member and assignment.member.user else None,
                        assignment.member.user.email if assignment.member and assignment.member.user else None,
                        assignment.memberId,
                    ),
                    email=assignment.member.user.email if assignment.member and assignment.member.user else None,
                )
                for assignment in project.members
            ],
            key=lambda item: item.name.lower(),
        )
        projects.append(
            AttendanceReportProjectOption(
                id=project.id,
                name=project.name,
                members=members,
            )
        )

    return AttendanceReportOptionsResponse(employees=employees, projects=projects)


async def list_attendance_report(
    db: AsyncSession,
    organization_id: str,
    *,
    date_from: date,
    date_to: date,
    project_id: str | None,
    employee_ids: list[str],
    page: int,
    page_size: int,
) -> tuple[list[AttendanceReportRowData], int, AttendanceReportSummaryData]:
    department_name = _department_name_subquery(organization_id)
    clock_out_description = _clock_out_description_subquery(organization_id)

    base_query = (
        select(
            AttendanceRecord.id,
            AttendanceRecord.employeeId,
            User.name,
            User.email,
            AttendanceRecord.date,
            AttendanceRecord.clockIn,
            AttendanceRecord.clockOut,
            AttendanceRecord.totalHours,
            AttendanceRecord.entryType,
            department_name.label("departmentName"),
            Project.name.label("projectName"),
            Project.clientName.label("clientName"),
            ProjectTask.name.label("taskName"),
            clock_out_description.label("clockOutDescription"),
            LeaveType.name.label("leaveTypeName"),
        )
        .join(Member, Member.id == AttendanceRecord.employeeId)
        .join(User, User.id == Member.userId)
        .outerjoin(Project, Project.id == AttendanceRecord.projectId)
        .outerjoin(ProjectTask, ProjectTask.id == AttendanceRecord.projectTaskId)
        .outerjoin(
            LeaveRequest,
            (LeaveRequest.organizationId == organization_id)
            & (LeaveRequest.memberId == AttendanceRecord.employeeId)
            & (LeaveRequest.status == "APPROVED")
            & (LeaveRequest.deletedAt.is_(None))
            & (LeaveRequest.startDate <= AttendanceRecord.date)
            & (LeaveRequest.endDate >= AttendanceRecord.date),
        )
        .outerjoin(LeaveType, LeaveType.id == LeaveRequest.leaveTypeId)
    )
    base_query = _apply_filters(
        base_query,
        organization_id,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        employee_ids=employee_ids,
    )

    count_query = (
        select(
            func.count(distinct(AttendanceRecord.id)),
            func.coalesce(func.sum(AttendanceRecord.totalHours), 0.0),
            func.count(distinct(AttendanceRecord.employeeId)),
        )
        .select_from(AttendanceRecord)
        .join(Member, Member.id == AttendanceRecord.employeeId)
        .join(User, User.id == Member.userId)
    )
    count_query = _apply_filters(
        count_query,
        organization_id,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        employee_ids=employee_ids,
    )
    total, total_hours, employee_count = (await db.execute(count_query)).one()

    result = await db.execute(
        base_query.order_by(AttendanceRecord.date.asc(), User.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = [
        AttendanceReportRowData(
            attendance_record_id=row.id,
            employee_id=row.employeeId,
            employee_name=_display_employee_name(row.name, row.email, row.employeeId),
            employee_email=row.email,
            day=row.date,
            clock_in=row.clockIn,
            clock_out=row.clockOut,
            total_hours=row.totalHours,
            department_name=row.departmentName,
            project_name=row.projectName,
            client_name=row.clientName,
            task_name=row.taskName,
            clock_out_description=row.clockOutDescription,
            leave_type_name=row.leaveTypeName,
            entry_type=row.entryType,
        )
        for row in result
    ]

    # Query approved leaves that do NOT have a matching attendance record
    existing_keys = {(r.employee_id, r.day) for r in rows}
    leaves_result = await db.execute(
        select(
            LeaveRequest.memberId,
            LeaveRequest.startDate,
            LeaveRequest.endDate,
            LeaveType.name.label("leaveTypeName"),
        )
        .join(LeaveType, LeaveType.id == LeaveRequest.leaveTypeId)
        .where(
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.status == "APPROVED",
            LeaveRequest.deletedAt.is_(None),
            LeaveRequest.startDate <= date_to,
            LeaveRequest.endDate >= date_from,
        )
    )
    from datetime import timedelta as _td

    for lr in leaves_result:
        member_id = lr.memberId
        lr_start = lr.startDate
        lr_end = lr.endDate
        leave_name = lr.leaveTypeName
        day = max(lr_start, date_from)
        end = min(lr_end, date_to)
        while day <= end:
            if (member_id, day) not in existing_keys:
                rows.append(
                    AttendanceReportRowData(
                        attendance_record_id="",
                        employee_id=member_id,
                        employee_name="",
                        employee_email=None,
                        day=day,
                        clock_in=None,
                        clock_out=None,
                        total_hours=0,
                        department_name=None,
                        project_name=None,
                        client_name=None,
                        task_name=None,
                        clock_out_description=None,
                        leave_type_name=leave_name,
                        entry_type=None,
                    )
                )
            day += _td(days=1)

    return (
        rows,
        int(total or 0),
        AttendanceReportSummaryData(
            total_days=int(total or 0),
            total_hours=round(float(total_hours or 0.0), 4),
            employee_count=int(employee_count or 0),
        ),
    )
