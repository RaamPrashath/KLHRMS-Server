from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.modules.attendance.schema import AttendanceListResponse
from app.modules.jobs.schema import JobRequisitionListItemRead
from app.modules.leave.schema import LeaveRequestListResponse, MemberSummaryResponse
from app.modules.weekly_plan.schema import WeeklyPlanRead


class DashboardCapabilities(BaseModel):
    attendance_overview: bool = Field(alias="attendanceOverview")
    leave_requests: bool = Field(alias="leaveRequests")
    jobs: bool

    model_config = {"populate_by_name": True}


class DashboardDepartmentSummary(BaseModel):
    id: str
    name: str
    role: str
    head_member_name: str | None = Field(default=None, alias="headMemberName")
    member_count: int = Field(alias="memberCount")

    model_config = {"populate_by_name": True}


class DashboardResponse(BaseModel):
    today: dt.date
    capabilities: DashboardCapabilities
    members: list[MemberSummaryResponse] = Field(default_factory=list)
    attendance_today: AttendanceListResponse | None = Field(default=None, alias="attendanceToday")
    approved_leaves_today: LeaveRequestListResponse | None = Field(default=None, alias="approvedLeavesToday")
    pending_leave_requests: LeaveRequestListResponse | None = Field(default=None, alias="pendingLeaveRequests")
    job_requisitions: list[JobRequisitionListItemRead] = Field(default_factory=list, alias="jobRequisitions")
    team_weekly_plan_today: list[WeeklyPlanRead] = Field(default_factory=list, alias="teamWeeklyPlanToday")
    my_departments: list[DashboardDepartmentSummary] = Field(default_factory=list, alias="myDepartments")

    model_config = {"populate_by_name": True}
