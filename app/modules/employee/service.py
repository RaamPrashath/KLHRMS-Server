"""
Employee service — business logic for the employee list.

Queries Members joined with User, Role, and today's AttendanceRecord.
All queries are scoped by organizationId.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, func as sa_func, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.attendance_record import AttendanceRecord
from app.models.employee import Employee
from app.models.member import Member
from app.models.role import Role
from app.models.user import User
from app.modules.employee.schema import (
    AttendanceTodayResponse,
    EmployeeDeletePreview,
    EmployeeDeleteResponse,
    EmployeeDeactivateResponse,
    EmployeeListFilters,
    EmployeeListItem,
    EmployeeListResponse,
    RoleBriefResponse,
    UpdateEmployeeRoleResponse,
)
from app.models.recruitment import StageEventParticipant, HiringTeamMember, StageEvent, EventStatus

logger = logging.getLogger("klhrms.employee.service")


async def list_employees(
    organization_id: str,
    filters: EmployeeListFilters,
    db: AsyncSession,
) -> EmployeeListResponse:
    page = max(1, filters.page)
    page_size = max(1, min(100, filters.page_size))

    # ── Base query: active members joined with User + Role ────────────────
    query = (
        select(Member, User, Role, Employee)
        .join(User, Member.userId == User.id)
        .outerjoin(Role, Member.roleId == Role.id)
        .outerjoin(
            Employee,
            (Employee.member_id == Member.id)
            & (Employee.organization_id == UUID(organization_id)),
        )
        .where(
            Member.organizationId == organization_id,
            Member.status == "ACTIVE",
        )
    )

    # ── Search filter ──────────────────────────────────────────────────────
    if filters.search:
        term = f"%{filters.search.strip()}%"
        query = query.where(
            or_(User.name.ilike(term), User.email.ilike(term))
        )

    # ── Role filter ────────────────────────────────────────────────────────
    if filters.role_id:
        query = query.where(Member.roleId == filters.role_id)

    # ── Attendance status filter ───────────────────────────────────────────
    if filters.attendance_status:
        today = date.today()
        query = query.join(
            AttendanceRecord,
            (AttendanceRecord.employeeId == Member.id)
            & (AttendanceRecord.date == today)
            & (AttendanceRecord.status == filters.attendance_status),
        )

    # ── Count total before pagination ───────────────────────────────────────
    count_query = select(sa_func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    total_pages = max(1, -(-total // page_size))

    # ── Paginate ───────────────────────────────────────────────────────────
    offset_val = (page - 1) * page_size
    query = query.order_by(User.name.asc()).offset(offset_val).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    # ── Batch fetch today's attendance ──────────────────────────────────────
    today = date.today()
    member_ids = [m.id for m, _, _, _ in rows]
    attendance_rows: dict[str, AttendanceRecord] = {}
    if member_ids:
        att_result = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employeeId.in_(member_ids),
                AttendanceRecord.date == today,
            )
        )
        for ar in att_result.scalars().all():
            attendance_rows[ar.employeeId] = ar

    # ── Batch fetch Microsoft sync status ──────────────────────────────────
    user_ids = [u.id for _, u, _, _ in rows]
    synced_user_ids: set[str] = set()
    if user_ids:
        acct_result = await db.execute(
            select(Account.userId).where(
                Account.providerId == "microsoft",
                Account.userId.in_(user_ids),
            )
        )
        synced_user_ids = {row[0] for row in acct_result}

    # ── Build response items ───────────────────────────────────────────────
    items: list[EmployeeListItem] = []
    for member, user, role, employee in rows:
        att = attendance_rows.get(member.id)
        image = user.image or (employee.profile_photo_url if employee else None)
        items.append(
            EmployeeListItem(
                member_id=member.id,
                user_id=user.id,
                name=user.name or user.email or "Unknown",
                email=user.email or "",
                image=image,
                role=RoleBriefResponse(id=role.id, name=role.name) if role else None,
                joined_at=member.createdAt.isoformat() if member.createdAt else "",
                attendance_today=AttendanceTodayResponse(
                    status=att.status if att else "NO_RECORD",
                    clock_in=att.clockIn.isoformat() if att and att.clockIn else None,
                    clock_out=att.clockOut.isoformat() if att and att.clockOut else None,
                ),
                microsoft_synced=user.id in synced_user_ids,
            )
        )

    return EmployeeListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def list_departments_for_org(organization_id: str, db: AsyncSession) -> list[dict]:
    """Return all departments for filter dropdown (placeholder until department module is complete)."""
    return []


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

    result = await db.execute(
        select(Member)
        .options(joinedload(Member.user))
        .where(Member.id == member_id)
    )
    member = result.unique().scalar_one_or_none()
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

    result = await db.execute(
        select(Member)
        .options(joinedload(Member.user))
        .where(Member.id == member_id)
    )
    member = result.unique().scalar_one_or_none()
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


async def deactivate_employee(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDeactivateResponse:
    """Set a member's status to INACTIVE (soft-delete)."""

    result = await db.execute(
        select(Member)
        .options(joinedload(Member.user))
        .where(Member.id == member_id)
    )
    member = result.unique().scalar_one_or_none()
    if member is None or member.organizationId != organization_id:
        raise HTTPException(status_code=404, detail="Employee not found")

    member.status = "INACTIVE"
    db.add(member)
    await db.commit()
    await db.refresh(member)

    user_name = member.user.name or member.user.email if member.user else "Unknown"

    return EmployeeDeactivateResponse(
        member_id=member.id,
        name=user_name,
        email=member.user.email if member.user else "",
        status=member.status,
    )


async def update_employee_role(
    organization_id: str,
    member_id: str,
    role_id: str,
    db: AsyncSession,
) -> UpdateEmployeeRoleResponse:
    result = await db.execute(
        select(Member)
        .options(joinedload(Member.user))
        .where(Member.id == member_id)
    )
    member = result.unique().scalar_one_or_none()
    if not member or member.organizationId != organization_id:
        raise HTTPException(status_code=404, detail="Employee not found")

    result = await db.execute(
        select(Role).where(Role.id == role_id, Role.organizationId == organization_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    member.roleId = role_id
    db.add(member)
    await db.commit()
    await db.refresh(member)

    user_name = member.user.name or member.user.email or "" if member.user else ""

    return UpdateEmployeeRoleResponse(
        member_id=member.id,
        name=user_name,
        role_id=role_id,
        role_name=role.name,
    )
