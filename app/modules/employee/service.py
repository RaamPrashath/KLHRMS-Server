"""
Employee service — business logic for the employee list.

Queries Members joined with User, Role, DepartmentMember/Department,
and today's AttendanceRecord in a single efficient query.
All queries are scoped by organizationId.
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.attendance_record import AttendanceRecord
from app.models.department import Department
from app.models.department_member import DepartmentMember
from app.models.member import Member
from app.models.role import Role
from app.models.user import User
from app.modules.employee.schema import (
    AttendanceTodayResponse,
    DepartmentBriefResponse,
    EmployeeListFilters,
    EmployeeListItem,
    EmployeeListResponse,
    RoleBriefResponse,
)


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
            joinedload(Member.departmentMembers).joinedload(DepartmentMember.department),
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
    if filters.department_id:
        base_q = base_q.join(
            DepartmentMember, Member.id == DepartmentMember.memberId
        ).where(DepartmentMember.departmentId == filters.department_id)

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

        # Pick the first department membership (most orgs have one per member)
        dept_membership: DepartmentMember | None = (
            member.departmentMembers[0] if member.departmentMembers else None
        )
        dept: Department | None = dept_membership.department if dept_membership else None

        attendance_today = _attendance_status_for_record(attendance_map.get(member.id))

        items.append(
            EmployeeListItem(
                member_id=member.id,
                user_id=user.id,
                name=user.name or user.email,
                email=user.email,
                image=user.image,
                role=RoleBriefResponse(id=role.id, name=role.name) if role else None,
                department=DepartmentBriefResponse(id=dept.id, name=dept.name) if dept else None,
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


async def list_departments_for_org(organization_id: str, db: AsyncSession) -> list[dict]:
    """Return all active departments for filter dropdown."""
    result = await db.execute(
        select(Department)
        .where(
            Department.organizationId == organization_id,
            Department.status == "ACTIVE",
        )
        .order_by(Department.name.asc())
    )
    rows = result.scalars().all()

    return [{"id": r.id, "name": r.name} for r in rows]


async def list_roles_for_org(organization_id: str, db: AsyncSession) -> list[dict]:
    """Return all roles for filter dropdown."""
    result = await db.execute(
        select(Role)
        .where(Role.organizationId == organization_id)
        .order_by(Role.name.asc())
    )
    rows = result.scalars().all()

    return [{"id": r.id, "name": r.name} for r in rows]
