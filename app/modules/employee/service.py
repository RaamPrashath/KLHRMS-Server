"""
Employee service — business logic for the employee list.

Queries Members joined with User, Role, and today's AttendanceRecord.
All queries are scoped by organizationId.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.attendance_record import AttendanceRecord
from app.models.member import Member
from app.models.role import Role
from app.models.user import User
from app.modules.employee.schema import (
    AttendanceTodayResponse,
    EmployeeDeletePreview,
    EmployeeDeleteResponse,
    EmployeeListFilters,
    EmployeeListItem,
    EmployeeListResponse,
    RoleBriefResponse,
)
from app.models.recruitment import StageEventParticipant, HiringTeamMember, StageEvent, EventStatus


def _attendance_status_for_record(record: AttendanceRecord | None) -> AttendanceTodayResponse:
    """Map an AttendanceRecord ORM row to the response DTO."""
    if record is None:
        return AttendanceTodayResponse(status="NO_RECORD")

    clock_in_str = record.clockIn.isoformat() if record.clockIn else None
    clock_out_str = record.clockOut.isoformat() if record.clockOut else None

    return AttendanceTodayResponse(
        status=record.status,
        clock_in=clock_in_str,
        clock_out=clock_out_str,
    )


async def list_employees(
    organization_id: str,
    filters: EmployeeListFilters,
    db: AsyncSession,
) -> EmployeeListResponse:
    """
    Return a paginated list of employees for the given organization.

    Joins:
      Member → User (name, email, image)
      Member → Role (name)
      Member → DepartmentMember → Department (name)
      Member → AttendanceRecord for today (status, clock_in, clock_out)

    Filters:
      search          — case-insensitive match on user name or email
      department_id   — filter by department
      role_id         — filter by role
      attendance_status — filter by today's attendance status
    """
    today = dt.date.today()

    # ── Base query: Members in this org with eager-loaded relations ────────────
    base_q = (
        select(Member)
        .where(Member.organizationId == organization_id)
        .options(
            joinedload(Member.user),
            joinedload(Member.role),
        )
    )

    # ── Search filter ──────────────────────────────────────────────────────────
    if filters.search:
        term = f"%{filters.search.strip()}%"
        base_q = base_q.join(User, Member.userId == User.id).where(
            or_(
                func.lower(User.name).like(func.lower(term)),
                func.lower(User.email).like(func.lower(term)),
            )
        )
    else:
        # Always join user so we can order by name
        base_q = base_q.join(User, Member.userId == User.id)

    # ── Department filter ──────────────────────────────────────────────────────
    # (department table not yet migrated — filter skipped)

    # ── Role filter ────────────────────────────────────────────────────────────
    if filters.role_id:
        base_q = base_q.where(Member.roleId == filters.role_id)

    # ── Count total (before pagination) ───────────────────────────────────────
    count_q = select(func.count()).select_from(base_q.subquery())
    total_result = await db.execute(count_q)
    total: int = total_result.scalar_one()

    # ── Pagination ─────────────────────────────────────────────────────────────
    page = max(1, filters.page)
    page_size = max(1, min(100, filters.page_size))
    offset = (page - 1) * page_size

    members_result = await db.execute(
        base_q.order_by(User.name.asc()).offset(offset).limit(page_size)
    )
    members: list[Member] = list(
        members_result.scalars().unique().all()
    )

    if not members:
        return EmployeeListResponse(
            items=[],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=max(1, -(-total // page_size)),
        )

    # ── Fetch today's attendance for all returned members in one query ─────────
    member_ids = [m.id for m in members]
    attendance_result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId.in_(member_ids),
            AttendanceRecord.date == today,
        )
    )
    attendance_rows: list[AttendanceRecord] = list(
        attendance_result.scalars().all()
    )
    attendance_map: dict[str, AttendanceRecord] = {r.employeeId: r for r in attendance_rows}

    # ── Attendance status filter (post-fetch) ──────────────────────────────────
    # We apply this after fetching to avoid a complex subquery join.
    # For large orgs this should be moved to a SQL-level filter.
    if filters.attendance_status:
        target_status = filters.attendance_status.upper()
        filtered_members: list[Member] = []
        for m in members:
            record = attendance_map.get(m.id)
            actual_status = record.status if record else "NO_RECORD"
            if actual_status == target_status:
                filtered_members.append(m)
        members = filtered_members

    # ── Build response items ───────────────────────────────────────────────────
    items: list[EmployeeListItem] = []
    for member in members:
        user: User = member.user
        role: Role | None = member.role

        attendance_today = _attendance_status_for_record(attendance_map.get(member.id))

        items.append(
            EmployeeListItem(
                member_id=member.id,
                user_id=user.id,
                name=user.name or user.email,
                email=user.email,
                image=user.image,
                role=RoleBriefResponse(id=role.id, name=role.name) if role else None,
                joined_at=member.createdAt.isoformat(),
                attendance_today=attendance_today,
            )
        )

    total_pages = max(1, -(-total // page_size))

    return EmployeeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def list_roles_for_org(organization_id: str, db: AsyncSession) -> list[dict]:
    """Return all roles for filter dropdown."""
    result = await db.execute(
        select(Role)
        .where(Role.organizationId == organization_id)
        .order_by(Role.name.asc())
    )
    rows = result.scalars().all()

    return [{"id": r.id, "name": r.name} for r in rows]


async def preview_employee_delete(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDeletePreview:
    """Preview what will happen when an employee is deleted."""
    from sqlalchemy import func, select

    member = await db.get(Member, member_id)
    if member is None or member.organizationId != organization_id:
        raise HTTPException(status_code=404, detail="Employee not found")

    user_name = member.user.name or member.user.email if member.user else "Unknown"

    # Count interview participants
    interview_count_result = await db.execute(
        select(func.count(StageEventParticipant.id)).where(
            StageEventParticipant.memberId == member_id,
        )
    )
    interview_count: int = interview_count_result.scalar_one()

    # Count team memberships
    team_count_result = await db.execute(
        select(func.count(HiringTeamMember.id)).where(
            HiringTeamMember.memberId == member_id,
        )
    )
    team_count: int = team_count_result.scalar_one()

    return EmployeeDeletePreview(
        member_id=member_id,
        name=user_name,
        email=member.user.email if member.user else "",
        interview_count=interview_count,
        team_membership_count=team_count,
    )


async def delete_employee(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDeleteResponse:
    """Delete an employee, unassigning all their interviews and removing team memberships."""
    from sqlalchemy import select

    member = await db.get(Member, member_id)
    if member is None or member.organizationId != organization_id:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Find all events where this member is a primary interviewer and unassign them
    participant_result = await db.execute(
        select(StageEventParticipant).where(
            StageEventParticipant.memberId == member_id,
        )
    )
    participants: list[StageEventParticipant] = list(participant_result.scalars().all())
    interview_count = len(participants)

    # For primary interviewers, set their events to UNASSIGNED
    for participant in participants:
        if not participant.isBackup and participant.role in ("INTERVIEWER", None):
            event_result = await db.execute(
                select(StageEvent).where(StageEvent.id == participant.eventId)
            )
            event = event_result.scalar_one_or_none()
            if event is not None:
                event.status = EventStatus.UNASSIGNED
                event.scheduledStartAt = None
                event.scheduledEndAt = None
                db.add(event)
        await db.delete(participant)

    # Count and delete team memberships
    team_result = await db.execute(
        select(HiringTeamMember).where(
            HiringTeamMember.memberId == member_id,
        )
    )
    team_memberships: list[HiringTeamMember] = list(team_result.scalars().all())
    team_count = len(team_memberships)
    for tm in team_memberships:
        await db.delete(tm)

    # Delete the member (will cascade to other records)
    await db.delete(member)
    await db.commit()

    return EmployeeDeleteResponse(
        member_id=member_id,
        unassigned_interviews=interview_count,
        removed_team_memberships=team_count,
    )
