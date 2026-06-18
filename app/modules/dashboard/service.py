from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department
from app.models.department_head import DepartmentHead
from app.models.department_member import DepartmentMember
from app.models.member import Member
from app.models.monthly_plan import MonthlyPlan
from app.models.user import User
from app.models.weekly_plan import WeeklyPlan
from app.modules.attendance import controller as attendance_controller
from app.modules.attendance import service as attendance_service
from app.modules.attendance.schema import AttendanceListResponse
from app.modules.dashboard.schema import (
    DashboardCapabilities,
    DashboardDepartmentSummary,
    DashboardResponse,
)
from app.modules.jobs.repository import JobRequisitionRepository
from app.modules.jobs.service import OPEN_REQUISITION_STATUSES, _serialize_requisition
from app.modules.leave import controller as leave_controller
from app.modules.leave import service as leave_service
from app.modules.leave.permissions import get_permission_scope as get_leave_permission_scope
from app.modules.leave.schema import LeaveRequestFilters, LeaveRequestListResponse, MemberSummaryResponse
from app.modules.weekly_plan.schema import WeeklyPlanRead
from app.shared.deps.organization_member import MemberContext
from app.shared.utils.permissions import get_permission_scope


async def _get_department_member_ids(db: AsyncSession, ctx: MemberContext) -> set[str]:
    dept_ids_subq = (
        select(DepartmentHead.departmentId)
        .where(DepartmentHead.memberId == ctx.member.id)
    )
    member_subq = (
        select(DepartmentMember.memberId)
        .where(DepartmentMember.departmentId.in_(dept_ids_subq))
    )
    head_subq = (
        select(DepartmentHead.memberId)
        .where(DepartmentHead.departmentId.in_(dept_ids_subq))
    )
    result = await db.execute(
        select(Member.id, Member.userId)
        .where(
            (Member.id.in_(member_subq) | Member.id.in_(head_subq)),
            Member.status == "ACTIVE",  # status: ACTIVE only
        )
    )
    return {row.id for row in result.all()}


async def _list_members(
    db: AsyncSession,
    organization_id: str,
    member_ids: set[str] | None = None,
) -> list[MemberSummaryResponse]:
    query = (
        select(Member, User.name, User.email)
        .join(User, User.id == Member.userId)
        .where(Member.organizationId == organization_id, Member.status == "ACTIVE")  # status: ACTIVE only
    )
    if member_ids is not None:
        query = query.where(Member.id.in_(member_ids))
    query = query.order_by(User.name.asc(), User.email.asc())
    result = await db.execute(query)
    return [
        MemberSummaryResponse(
            memberId=member.id,
            userId=member.userId,
            name=name,
            email=email,
        )
        for member, name, email in result.all()
    ]


async def _get_attendance_today(
    db: AsyncSession,
    ctx: MemberContext,
    today: dt.date,
    scope: str = "organization",
) -> AttendanceListResponse:
    rows, total = await attendance_service.list_attendance(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        scope=scope,
        date_from=today,
        date_to=today,
        page=1,
        page_size=200,
    )
    return AttendanceListResponse(
        items=[attendance_controller._to_response(record, name) for record, name in rows],
        total=total,
        page=1,
        page_size=200,
    )


async def _get_leave_requests(
    db: AsyncSession,
    ctx: MemberContext,
    filters: LeaveRequestFilters,
    scope: str = "organization",
) -> LeaveRequestListResponse:
    items, total = await leave_service.list_leave_requests(
        db,
        ctx.organization.id,
        ctx.member.id,
        scope,
        filters,
    )
    return LeaveRequestListResponse(
        items=[leave_controller._leave_request_response(item) for item in items],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


async def _get_team_weekly_plan_today(
    db: AsyncSession,
    organization_id: str,
    today: dt.date,
    member_user_ids: set[str] | None = None,
) -> list[WeeklyPlanRead]:
    org_uuid = UUID(organization_id)
    rows: dict[str, tuple[WeeklyPlan | MonthlyPlan, str | None]] = {}

    for model in (MonthlyPlan, WeeklyPlan):
        query = (
            select(model, User.name.label("user_name"))
            .outerjoin(User, User.id == model.user_id)
            .where(
                model.organization_id == org_uuid,
                model.date == today,
                model.deleted_at.is_(None),
            )
        )
        if member_user_ids is not None:
            query = query.where(model.user_id.in_(member_user_ids))
        result = await db.execute(query)
        for entry, user_name in result.all():
            current = rows.get(entry.user_id)
            if current is None or entry.updatedAt >= current[0].updatedAt:
                rows[entry.user_id] = (entry, user_name)

    return [
        WeeklyPlanRead(
            id=entry.id,
            organization_id=entry.organization_id,
            user_id=entry.user_id,
            user_name=user_name,
            date=entry.date,
            work_location=entry.work_location,
            project=entry.project,
        )
        for entry, user_name in rows.values()
    ]


async def _get_open_job_requisitions(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
):
    repository = JobRequisitionRepository(db)
    requisitions = await repository.list_requisitions_by_statuses(
        organization_id,
        OPEN_REQUISITION_STATUSES,
    )
    return [_serialize_requisition(requisition, actor_member_id) for requisition in requisitions]


async def _get_my_departments(
    db: AsyncSession,
    ctx: MemberContext,
) -> list[DashboardDepartmentSummary]:
    member_department_rows = await db.execute(
        select(Department.id, Department.name)
        .join(DepartmentMember, DepartmentMember.departmentId == Department.id)
        .where(
            Department.organizationId == ctx.organization.id,
            Department.status == "ACTIVE",
            DepartmentMember.memberId == ctx.member.id,
        )
    )
    head_department_rows = await db.execute(
        select(Department.id, Department.name)
        .join(DepartmentHead, DepartmentHead.departmentId == Department.id)
        .where(
            Department.organizationId == ctx.organization.id,
            Department.status == "ACTIVE",
            DepartmentHead.memberId == ctx.member.id,
        )
    )

    departments: dict[str, dict[str, str]] = {}
    for department_id, department_name in member_department_rows.all():
        departments[department_id] = {"name": department_name, "role": "MEMBER"}
    for department_id, department_name in head_department_rows.all():
        departments[department_id] = {"name": department_name, "role": "HEAD"}

    if not departments:
        return []

    department_ids = list(departments.keys())
    head_rows = await db.execute(
        select(DepartmentHead.departmentId, User.name, User.email)
        .join(Member, Member.id == DepartmentHead.memberId)
        .join(User, User.id == Member.userId)
        .where(DepartmentHead.departmentId.in_(department_ids))
        .order_by(User.name.asc().nullslast(), User.email.asc())
    )
    head_names: dict[str, str] = {}
    for department_id, name, email in head_rows.all():
        if department_id not in head_names:
            head_names[department_id] = name or email or "Unnamed head"

    member_count_rows = await db.execute(
        select(DepartmentMember.departmentId, DepartmentMember.memberId)
        .where(DepartmentMember.departmentId.in_(department_ids))
    )
    head_count_rows = await db.execute(
        select(DepartmentHead.departmentId, DepartmentHead.memberId)
        .where(DepartmentHead.departmentId.in_(department_ids))
    )
    member_ids_by_department: dict[str, set[str]] = {department_id: set() for department_id in department_ids}
    for department_id, member_id in member_count_rows.all():
        member_ids_by_department.setdefault(department_id, set()).add(member_id)
    for department_id, member_id in head_count_rows.all():
        member_ids_by_department.setdefault(department_id, set()).add(member_id)

    return [
        DashboardDepartmentSummary(
            id=department_id,
            name=data["name"],
            role=data["role"],
            headMemberName=head_names.get(department_id),
            memberCount=len(member_ids_by_department.get(department_id, set())),
        )
        for department_id, data in sorted(departments.items(), key=lambda item: item[1]["name"].lower())
    ]


async def get_dashboard(
    db: AsyncSession,
    ctx: MemberContext,
    today: dt.date,
) -> DashboardResponse:
    permissions = ctx.role.permissions if isinstance(ctx.role.permissions, dict) else {}

    attendance_view_scope = get_permission_scope(permissions, "attendance", "view")
    leave_view_scope = get_leave_permission_scope(permissions, "leaves", "view")
    leave_approve_scope = get_leave_permission_scope(permissions, "leaves", "approve")
    weekly_plan_view_scope = get_permission_scope(permissions, "weeklyPlan", "view")

    can_show_attendance = attendance_view_scope in ("organization", "department") and leave_view_scope in ("organization", "department")
    can_show_leave_requests = leave_approve_scope in ("organization", "department")

    members: list[MemberSummaryResponse] = []
    attendance_today: AttendanceListResponse | None = None
    approved_leaves_today: LeaveRequestListResponse | None = None
    pending_leave_requests: LeaveRequestListResponse | None = None
    team_weekly_plan_today: list[WeeklyPlanRead] = []
    my_departments = await _get_my_departments(db, ctx)

    effective_scope = attendance_view_scope if attendance_view_scope in ("organization", "department") else "organization"
    department_member_ids: set[str] | None = None
    department_user_ids: set[str] | None = None

    if can_show_attendance:
        if effective_scope == "department":
            department_member_ids = await _get_department_member_ids(db, ctx)
            dept_user_result = await db.execute(
                select(Member.userId).where(Member.id.in_(department_member_ids))
            )
            department_user_ids = {row.userId for row in dept_user_result.all()}

        members = await _list_members(db, ctx.organization.id, department_member_ids)
        attendance_today = await _get_attendance_today(db, ctx, today, effective_scope)
        approved_leaves_today = await _get_leave_requests(
            db,
            ctx,
            LeaveRequestFilters(
                status="APPROVED",
                fromDate=today,
                toDate=today,
                page=1,
                page_size=200,
            ),
            effective_scope,
        )
        if weekly_plan_view_scope in ("organization", "department"):
            team_weekly_plan_today = await _get_team_weekly_plan_today(
                db, ctx.organization.id, today, department_user_ids,
            )

    if can_show_leave_requests:
        pending_leave_scope = leave_approve_scope if leave_approve_scope in ("organization", "department") else "organization"
        pending_leave_requests = await _get_leave_requests(
            db,
            ctx,
            LeaveRequestFilters(status="PENDING", page=1, page_size=3),
            pending_leave_scope,
        )

    job_requisitions = await _get_open_job_requisitions(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
    )

    return DashboardResponse(
        today=today,
        capabilities=DashboardCapabilities(
            attendanceOverview=can_show_attendance,
            leaveRequests=can_show_leave_requests,
            jobs=True,
        ),
        members=members,
        attendanceToday=attendance_today,
        approvedLeavesToday=approved_leaves_today,
        pendingLeaveRequests=pending_leave_requests,
        jobRequisitions=job_requisitions,
        teamWeeklyPlanToday=team_weekly_plan_today,
        myDepartments=my_departments,
    )
