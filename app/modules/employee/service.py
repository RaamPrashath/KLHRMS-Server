"""
Employee service — business logic for the employee list.

Queries Members joined with User, Role, and today's AttendanceRecord.
All queries are scoped by organizationId.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, func as sa_func, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.microsoft_graph.exceptions import (
    MicrosoftGraphConfigurationError,
)
from app.integrations.microsoft_graph.graph_client import MicrosoftGraphClient
from app.integrations.microsoft_graph.token_manager import TokenManager
from app.models.account import Account
from app.models.attendance_record import AttendanceRecord
from app.models.department_head import DepartmentHead
from app.models.department_member import DepartmentMember
from app.models.employee import Employee
from app.models.employee_group import EmployeeGroup
from app.models.employee_group_membership import EmployeeGroupMembership
from app.models.member import Member
from app.models.microsoft_integration_setting import MicrosoftIntegrationSetting
from app.models.role import Role
from app.models.user import User
from app.modules.employee.schema import (
    AttendanceTodayResponse,
    EmployeeAddress,
    EmployeeContactInfo,
    EmployeeDeletePreview,
    EmployeeDeleteResponse,
    EmployeeDeactivateResponse,
    EmployeeDetailResponse,
    EmployeeDirectReportsResponse,
    EmployeeEmployment,
    EmployeeGroupBrief,
    EmployeeGroupListResponse,
    EmployeeManagerChainResponse,
    EmployeePersonBrief,
    EmployeeRefreshResponse,
    EmployeeSyncInfo,
    EmployeeListFilters,
    EmployeeListItem,
    EmployeeListResponse,
    RoleBriefResponse,
    UpdateEmployeeDetailsRequest,
    UpdateEmployeeDetailsResponse,
    UpdateEmployeeRoleResponse,
)
from app.models.recruitment import StageEventParticipant, HiringTeamMember, StageEvent, EventStatus
from app.shared.config import get_settings

logger = logging.getLogger("klhrms.employee.service")


async def list_employees(
    organization_id: str,
    db: AsyncSession,
    scope: str = "organization",
    actor_member_id: str | None = None,
) -> EmployeeListResponse:
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

    # ── Department scope: filter to members + heads in actor's departments ─
    if scope == "department" and actor_member_id:
        dept_result = await db.execute(
            select(DepartmentHead.departmentId).where(
                DepartmentHead.memberId == actor_member_id,
            )
        )
        dept_ids = [row[0] for row in dept_result.all()]
        if dept_ids:
            member_in_dept = (
                select(DepartmentMember.memberId)
                .where(DepartmentMember.departmentId.in_(dept_ids))
            )
            head_in_dept = (
                select(DepartmentHead.memberId)
                .where(DepartmentHead.departmentId.in_(dept_ids))
            )
            query = query.where(
                Member.id.in_(member_in_dept) |
                Member.id.in_(head_in_dept)
            )
        else:
            query = query.where(sa_func.false())

    query = query.order_by(
        sa_func.lower(
            sa_func.coalesce(
                Employee.display_name,
                User.name,
                Employee.email,
                User.email,
                Employee.user_principal_name,
                Member.id,
            )
        )
    )

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
        display_name = (
            (employee.display_name if employee else None)
            or user.name
            or (employee.email if employee else None)
            or user.email
            or (employee.user_principal_name if employee else None)
            or "Unknown"
        )
        primary_email = (
            (employee.email if employee else None)
            or user.email
            or (employee.user_principal_name if employee else None)
            or ""
        )
        items.append(
            EmployeeListItem(
                member_id=member.id,
                user_id=user.id,
                name=display_name,
                email=primary_email,
                image=image,
                user_principal_name=employee.user_principal_name if employee else None,
                role=RoleBriefResponse(id=role.id, name=role.name) if role else None,
                employee_id=employee.employee_id if employee else None,
                department=employee.department_name if employee else None,
                job_title=employee.job_title if employee else None,
                joined_at=member.createdAt.isoformat() if member.createdAt else "",
                attendance_today=AttendanceTodayResponse(
                    status=att.status if att else "NO_RECORD",
                    clock_in=att.clockIn.isoformat() if att and att.clockIn else None,
                    clock_out=att.clockOut.isoformat() if att and att.clockOut else None,
                ),
                microsoft_synced=user.id in synced_user_ids,
            )
        )

    total = len(items)
    return EmployeeListResponse(
        items=items,
        total=total,
        page=1,
        page_size=total,
        total_pages=1,
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


# ─── Employee Detail (Microsoft Entra enriched) ────────────────────────────────


def _to_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
    return s or None


def _to_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _build_person_brief_from_employee(employee: Employee) -> EmployeePersonBrief:
    return EmployeePersonBrief(
        member_id=employee.member_id,
        user_id=employee.user_id,
        name=employee.display_name or "Unknown",
        email=employee.email,
        job_title=employee.job_title,
        department=employee.department_name,
        image=employee.profile_photo_url,
        microsoft_id=employee.microsoft_id,
    )


def _build_chain_entry_from_employee(
    employee: Employee,
) -> dict[str, Any]:
    return {
        "graph_id": employee.microsoft_id,
        "display_name": employee.display_name,
        "user_principal_name": employee.user_principal_name,
        "job_title": employee.job_title,
        "department": employee.department_name,
        "mail": employee.email,
        "member_id": employee.member_id,
    }


async def _get_employee_entity(
    organization_id: str, member_id: str, db: AsyncSession
) -> Employee | None:
    result = await db.execute(
        select(Employee).where(
            Employee.organization_id == UUID(organization_id),
            Employee.member_id == member_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_member_with_user(
    organization_id: str, member_id: str, db: AsyncSession
) -> tuple[Member, User]:
    result = await db.execute(
        select(Member)
        .options(joinedload(Member.user), joinedload(Member.role))
        .where(Member.id == member_id)
    )
    member = result.unique().scalar_one_or_none()
    if member is None or member.organizationId != organization_id:
        raise HTTPException(status_code=404, detail="Employee not found")
    if member.user is None:
        raise HTTPException(status_code=404, detail="Employee user record missing")
    return member, member.user


async def _get_today_attendance(member_id: str, db: AsyncSession) -> AttendanceRecord | None:
    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.employeeId == member_id,
            AttendanceRecord.date == date.today(),
        )
    )
    return result.scalar_one_or_none()


async def get_employee_detail(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDetailResponse:
    member, user = await _get_member_with_user(organization_id, member_id, db)
    employee = await _get_employee_entity(organization_id, member_id, db)
    attendance = await _get_today_attendance(member_id, db)

    manager_brief: Optional[EmployeePersonBrief] = None
    direct_reports: list[EmployeePersonBrief] = []
    groups: list[EmployeeGroupBrief] = []
    manager_chain: list[dict[str, Any]] = []

    if employee is not None:
        # Manager (direct)
        if employee.manager_id is not None:
            result = await db.execute(
                select(Employee).where(
                    Employee.organization_id == UUID(organization_id),
                    Employee.id == employee.manager_id,
                )
            )
            mgr = result.scalar_one_or_none()
            if mgr is not None:
                manager_brief = _build_person_brief_from_employee(mgr)

        # Direct reports
        dr_result = await db.execute(
            select(Employee).where(
                Employee.organization_id == UUID(organization_id),
                Employee.manager_id == employee.id,
            )
        )
        direct_reports = [
            _build_person_brief_from_employee(e) for e in dr_result.scalars().all()
        ]

        # Group memberships
        if employee.id is not None:
            grp_result = await db.execute(
                select(EmployeeGroup)
                .join(
                    EmployeeGroupMembership,
                    EmployeeGroupMembership.group_id == EmployeeGroup.id,
                )
                .where(
                    EmployeeGroup.organization_id == UUID(organization_id),
                    EmployeeGroupMembership.employee_id == employee.id,
                )
                .order_by(EmployeeGroup.display_name.asc())
            )
            groups = [
                EmployeeGroupBrief(
                    id=str(g.id),
                    display_name=g.display_name,
                    description=g.description,
                    group_type=g.group_type,
                )
                for g in grp_result.scalars().all()
            ]

        # Manager chain
        if employee.manager_chain:
            for entry in employee.manager_chain:
                graph_id = entry.get("graph_id") if isinstance(entry, dict) else None
                if not graph_id:
                    continue
                res = await db.execute(
                    select(Employee).where(
                        Employee.organization_id == UUID(organization_id),
                        Employee.microsoft_id == graph_id,
                    )
                )
                m = res.scalar_one_or_none()
                if m is not None:
                    manager_chain.append(_build_chain_entry_from_employee(m))
                else:
                    manager_chain.append(
                        {
                            "graph_id": graph_id,
                            "display_name": entry.get("display_name", ""),
                            "user_principal_name": entry.get("user_principal_name"),
                            "job_title": entry.get("job_title"),
                            "department": entry.get("department"),
                            "mail": entry.get("mail"),
                        }
                    )

    image = user.image or (employee.profile_photo_url if employee else None)
    role_brief = (
        RoleBriefResponse(id=member.role.id, name=member.role.name)
        if member.role
        else None
    )

    return EmployeeDetailResponse(
        member_id=member.id,
        user_id=user.id,
        name=(
            (employee.display_name if employee else None)
            or user.name
            or (employee.email if employee else None)
            or user.email
            or "Unknown"
        ),
        given_name=employee.given_name if employee else None,
        surname=employee.surname if employee else None,
        image=image,
        profile_photo_url=employee.profile_photo_url if employee else None,
        contact=EmployeeContactInfo(
            email=user.email or (employee.email if employee else None),
            user_principal_name=employee.user_principal_name if employee else None,
            mobile_phone=employee.mobile_phone if employee else None,
            business_phones=_to_list(employee.business_phones) if employee else [],
            office_location=employee.office_location if employee else None,
        ),
        address=EmployeeAddress(
            street=employee.street_address if employee else None,
            city=employee.city if employee else None,
            state=employee.state if employee else None,
            postal_code=employee.postal_code if employee else None,
            country=employee.country if employee else None,
        )
        if employee and any(
            getattr(employee, f, None)
            for f in ("street_address", "city", "state", "postal_code", "country")
        )
        else None,
        employment=EmployeeEmployment(
            employee_id=employee.employee_id if employee else None,
            job_title=employee.job_title if employee else None,
            department=employee.department_name if employee else None,
            company_name=employee.company_name if employee else None,
            employee_type=employee.employee_type if employee else None,
            hire_date=_to_optional_str(employee.employee_hire_date) if employee else None,
            usage_location=employee.usage_location if employee else None,
            user_type=employee.user_type if employee else None,
            preferred_language=employee.preferred_language if employee else None,
        ),
        role=role_brief,
        manager=manager_brief,
        direct_reports=direct_reports,
        manager_chain=manager_chain,
        groups=groups,
        sync=EmployeeSyncInfo(
            microsoft_id=employee.microsoft_id if employee else None,
            synced_at=_to_optional_str(employee.synced_at) if employee else None,
            created_date_time=_to_optional_str(employee.created_date_time) if employee else None,
            account_enabled=employee.account_enabled if employee else True,
            status=employee.status if employee else "ACTIVE",
        ),
        attendance_today=AttendanceTodayResponse(
            status=attendance.status if attendance else "NO_RECORD",
            clock_in=attendance.clockIn.isoformat() if attendance and attendance.clockIn else None,
            clock_out=attendance.clockOut.isoformat() if attendance and attendance.clockOut else None,
        ),
        joined_at=member.createdAt.isoformat() if member.createdAt else "",
    )


async def get_employee_direct_reports(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDirectReportsResponse:
    employee = await _get_employee_entity(organization_id, member_id, db)
    if employee is None or employee.id is None:
        return EmployeeDirectReportsResponse(member_id=member_id, direct_reports=[])
    result = await db.execute(
        select(Employee).where(
            Employee.organization_id == UUID(organization_id),
            Employee.manager_id == employee.id,
        )
    )
    return EmployeeDirectReportsResponse(
        member_id=member_id,
        direct_reports=[
            _build_person_brief_from_employee(e) for e in result.scalars().all()
        ],
    )


async def get_employee_group_memberships(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeGroupListResponse:
    employee = await _get_employee_entity(organization_id, member_id, db)
    if employee is None or employee.id is None:
        return EmployeeGroupListResponse(member_id=member_id, groups=[])
    result = await db.execute(
        select(EmployeeGroup)
        .join(
            EmployeeGroupMembership,
            EmployeeGroupMembership.group_id == EmployeeGroup.id,
        )
        .where(
            EmployeeGroup.organization_id == UUID(organization_id),
            EmployeeGroupMembership.employee_id == employee.id,
        )
        .order_by(EmployeeGroup.display_name.asc())
    )
    return EmployeeGroupListResponse(
        member_id=member_id,
        groups=[
            EmployeeGroupBrief(
                id=str(g.id),
                display_name=g.display_name,
                description=g.description,
                group_type=g.group_type,
            )
            for g in result.scalars().all()
        ],
    )


async def get_employee_manager_chain(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeManagerChainResponse:
    employee = await _get_employee_entity(organization_id, member_id, db)
    chain: list[dict[str, Any]] = []
    if employee and employee.manager_chain:
        for entry in employee.manager_chain:
            graph_id = entry.get("graph_id") if isinstance(entry, dict) else None
            if not graph_id:
                continue
            res = await db.execute(
                select(Employee).where(
                    Employee.organization_id == UUID(organization_id),
                    Employee.microsoft_id == graph_id,
                )
            )
            m = res.scalar_one_or_none()
            if m is not None:
                chain.append(_build_chain_entry_from_employee(m))
            else:
                chain.append(
                    {
                        "graph_id": graph_id,
                        "display_name": entry.get("display_name", ""),
                        "user_principal_name": entry.get("user_principal_name"),
                        "job_title": entry.get("job_title"),
                        "department": entry.get("department"),
                        "mail": entry.get("mail"),
                    }
                )
    return EmployeeManagerChainResponse(member_id=member_id, manager_chain=chain)


async def _resolve_graph_credentials(
    organization_id: str, db: AsyncSession
) -> dict[str, str]:
    result = await db.execute(
        select(MicrosoftIntegrationSetting).where(
            MicrosoftIntegrationSetting.organization_id == UUID(organization_id)
        )
    )
    setting = result.scalar_one_or_none()
    if setting and setting.is_enabled and setting.client_secret:
        return {
            "tenant_id": setting.tenant_id,
            "client_id": setting.client_id,
            "client_secret": setting.client_secret,
        }
    env = get_settings()
    if env.azure_tenant_id and env.azure_client_id and env.azure_client_secret:
        return {
            "tenant_id": env.azure_tenant_id,
            "client_id": env.azure_client_id,
            "client_secret": env.azure_client_secret,
        }
    raise MicrosoftGraphConfigurationError(
        "Microsoft Graph not configured for this organization"
    )


async def refresh_employee_from_graph(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeRefreshResponse:
    """Pull the latest profile, manager chain, and direct reports for one employee."""
    employee = await _get_employee_entity(organization_id, member_id, db)
    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee not synced from Microsoft yet. Run a full sync first.",
        )
    if not employee.microsoft_id:
        raise HTTPException(
            status_code=400,
            detail="Employee has no Microsoft identifier — cannot refresh",
        )

    creds = await _resolve_graph_credentials(organization_id, db)
    tm = TokenManager(creds["tenant_id"], creds["client_id"], creds["client_secret"])
    client = MicrosoftGraphClient(tm)

    # Profile
    profile = await client.get_user(employee.microsoft_id)
    if profile is not None:
        employee.given_name = profile.given_name
        employee.surname = profile.surname
        employee.display_name = profile.display_name or employee.display_name
        employee.user_principal_name = profile.user_principal_name
        employee.email = profile.email or employee.email
        employee.employee_id = profile.employee_id
        employee.department_name = profile.department
        employee.job_title = profile.job_title
        employee.mobile_phone = profile.mobile_phone
        employee.business_phones = profile.business_phones
        employee.office_location = profile.office_location
        employee.street_address = profile.street_address
        employee.city = profile.city
        employee.state = profile.state
        employee.postal_code = profile.postal_code
        employee.country = profile.country
        employee.company_name = profile.company_name
        employee.employee_type = profile.employee_type
        employee.employee_hire_date = profile.employee_hire_date
        employee.usage_location = profile.usage_location
        employee.user_type = profile.user_type
        employee.preferred_language = profile.preferred_language
        employee.created_date_time = profile.created_date_time
        employee.account_enabled = profile.account_enabled
        employee.status = "ACTIVE" if profile.account_enabled else "INACTIVE"

    # Manager chain (up to 12)
    chain: list[dict[str, Any]] = []
    visited: set[str] = set()
    current_id: Optional[str] = employee.microsoft_id
    for _ in range(12):
        if not current_id or current_id in visited:
            break
        visited.add(current_id)
        try:
            manager = await client.get_user_manager(current_id)
        except Exception:
            break
        if manager is None or not manager.graph_id:
            break
        chain.append(
            {
                "graph_id": manager.graph_id,
                "display_name": manager.display_name,
                "user_principal_name": manager.user_principal_name,
                "job_title": manager.job_title,
                "department": manager.department,
                "mail": manager.mail,
            }
        )
        current_id = manager.graph_id
    employee.manager_chain = chain or None

    # Resolve direct manager (top of chain) to local employee
    manager_resolved = False
    if chain:
        top = chain[0]
        result = await db.execute(
            select(Employee).where(
                Employee.organization_id == UUID(organization_id),
                Employee.microsoft_id == top.get("graph_id", ""),
            )
        )
        m = result.scalar_one_or_none()
        if m is not None:
            employee.manager_id = m.id
            manager_resolved = True
        else:
            employee.manager_id = None
    else:
        employee.manager_id = None

    # Direct reports (live)
    try:
        await client.get_user_direct_reports(employee.microsoft_id)
    except Exception:
        pass

    employee.synced_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(employee)

    # Count local direct reports
    dr_count_result = await db.execute(
        select(sa_func.count(Employee.id)).where(
            Employee.organization_id == UUID(organization_id),
            Employee.manager_id == employee.id,
        )
    )
    direct_reports_count = int(dr_count_result.scalar() or 0)

    # Count group memberships
    groups_count = 0
    if employee.id is not None:
        gc_result = await db.execute(
            select(sa_func.count(EmployeeGroupMembership.id)).where(
                EmployeeGroupMembership.employee_id == employee.id
            )
        )
        groups_count = int(gc_result.scalar() or 0)

    return EmployeeRefreshResponse(
        member_id=member_id,
        synced_at=employee.synced_at.isoformat() if employee.synced_at else "",
        direct_reports_count=direct_reports_count,
        groups_count=groups_count,
        manager_resolved=manager_resolved,
    )


# ─── Employee Update (admin overrides) ─────────────────────────────────────────

_EDITABLE_FIELDS = (
    "display_name",
    "given_name",
    "surname",
    "job_title",
    "department_name",
    "mobile_phone",
    "office_location",
    "employee_type",
    "employee_hire_date",
    "usage_location",
    "company_name",
    "employee_id",
    "street_address",
    "city",
    "state",
    "postal_code",
    "country",
)


async def update_employee_details(
    organization_id: str,
    member_id: str,
    payload: UpdateEmployeeDetailsRequest,
    db: AsyncSession,
) -> UpdateEmployeeDetailsResponse:
    """Apply admin-edited overrides to an employee record.

    Only fields explicitly provided in the request (non-None) are updated.
    Empty strings are accepted to clear a field; only ``None`` skips a field.
    If no Employee record exists yet, a new one is created with the updated
    values + the member_id / organization_id.
    """
    member, user = await _get_member_with_user(organization_id, member_id, db)
    employee = await _get_employee_entity(organization_id, member_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return _build_update_response(member, user, employee)

    if employee is None:
        # No employee record yet — create a minimal one with the update values
        employee_create_data = {
            "organization_id": UUID(organization_id),
            "member_id": member_id,
            "user_id": user.id,
            "microsoft_id": f"manual:{member_id}",
            "display_name": user.name or user.email or "Unknown",
            "status": "ACTIVE",
            "account_enabled": True,
        }
        employee_create_data.update(
            {
                k: v
                for k, v in update_data.items()
                if k in _EDITABLE_FIELDS
            }
        )
        employee = Employee(
            **employee_create_data,
        )
        db.add(employee)
    else:
        for key, value in update_data.items():
            if key in _EDITABLE_FIELDS and hasattr(employee, key):
                setattr(employee, key, value)
        employee.synced_at = datetime.now(timezone.utc)

    if employee is not None and (
        "display_name" not in update_data
        and ("given_name" in update_data or "surname" in update_data)
    ):
        parts = [
            (employee.given_name or "").strip(),
            (employee.surname or "").strip(),
        ]
        recomputed_name = " ".join(part for part in parts if part)
        if recomputed_name:
            employee.display_name = recomputed_name

    await db.commit()
    await db.refresh(employee)

    return _build_update_response(member, user, employee)


def _build_update_response(
    member: Member,
    user: User,
    employee: Employee | None,
) -> UpdateEmployeeDetailsResponse:
    name = (
        user.name
        or user.email
        or (employee.display_name if employee else None)
        or "Unknown"
    )
    contact = EmployeeContactInfo(
        email=user.email or (employee.email if employee else None),
        user_principal_name=employee.user_principal_name if employee else None,
        mobile_phone=employee.mobile_phone if employee else None,
        business_phones=_to_list(employee.business_phones) if employee else [],
        office_location=employee.office_location if employee else None,
    )
    employment = EmployeeEmployment(
        employee_id=employee.employee_id if employee else None,
        job_title=employee.job_title if employee else None,
        department=employee.department_name if employee else None,
        company_name=employee.company_name if employee else None,
        employee_type=employee.employee_type if employee else None,
        hire_date=_to_optional_str(employee.employee_hire_date) if employee else None,
        usage_location=employee.usage_location if employee else None,
        user_type=employee.user_type if employee else None,
        preferred_language=employee.preferred_language if employee else None,
    )
    return UpdateEmployeeDetailsResponse(
        member_id=member.id,
        name=name,
        employment=employment,
        contact=contact,
        synced_at=_to_optional_str(employee.synced_at) if employee else None,
    )
