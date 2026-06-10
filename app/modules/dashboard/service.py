from __future__ import annotations

import datetime as dt
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.models.monthly_plan import MonthlyPlan
from app.models.user import User
from app.models.weekly_plan import WeeklyPlan
from app.modules.attendance import controller as attendance_controller
from app.modules.attendance import service as attendance_service
from app.modules.attendance.schema import AttendanceListResponse
from app.modules.dashboard.schema import DashboardCapabilities, DashboardResponse
from app.modules.jobs.repository import JobRequisitionRepository
from app.modules.jobs.service import OPEN_REQUISITION_STATUSES, _serialize_requisition
from app.modules.leave import controller as leave_controller
from app.modules.leave import service as leave_service
from app.modules.leave.permissions import get_permission_scope as get_leave_permission_scope
from app.modules.leave.schema import LeaveRequestFilters, LeaveRequestListResponse, MemberSummaryResponse
from app.modules.weekly_plan.schema import WeeklyPlanRead
from app.shared.deps.organization_member import MemberContext
from app.shared.utils.permissions import get_permission_scope


async def _list_members(db: AsyncSession, organization_id: str) -> list[MemberSummaryResponse]:
    result = await db.execute(
        select(Member, User.name, User.email)
        .join(User, User.id == Member.userId)
        .where(Member.organizationId == organization_id)
        .order_by(User.name.asc(), User.email.asc())
    )
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
) -> AttendanceListResponse:
    rows, total = await attendance_service.list_attendance(
        db=db,
        organization_id=ctx.organization.id,
        actor_member_id=ctx.member.id,
        scope="organization",
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
) -> LeaveRequestListResponse:
    items, total = await leave_service.list_leave_requests(
        db,
        ctx.organization.id,
        ctx.member.id,
        "organization",
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
) -> list[WeeklyPlanRead]:
    org_uuid = UUID(organization_id)
    rows: dict[str, tuple[WeeklyPlan | MonthlyPlan, str | None]] = {}

    for model in (MonthlyPlan, WeeklyPlan):
        result = await db.execute(
            select(model, User.name.label("user_name"))
            .outerjoin(User, User.id == model.user_id)
            .where(
                model.organization_id == org_uuid,
                model.date == today,
                model.deleted_at.is_(None),
            )
        )
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

    can_show_attendance = attendance_view_scope == "organization" and leave_view_scope == "organization"
    can_show_leave_requests = leave_approve_scope == "organization"

    members: list[MemberSummaryResponse] = []
    attendance_today: AttendanceListResponse | None = None
    approved_leaves_today: LeaveRequestListResponse | None = None
    pending_leave_requests: LeaveRequestListResponse | None = None
    team_weekly_plan_today: list[WeeklyPlanRead] = []

    if can_show_attendance:
        members = await _list_members(db, ctx.organization.id)
        attendance_today = await _get_attendance_today(db, ctx, today)
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
        )
        if weekly_plan_view_scope == "organization":
            team_weekly_plan_today = await _get_team_weekly_plan_today(db, ctx.organization.id, today)

    if can_show_leave_requests:
        pending_leave_requests = await _get_leave_requests(
            db,
            ctx,
            LeaveRequestFilters(status="PENDING", page=1, page_size=3),
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
    )
