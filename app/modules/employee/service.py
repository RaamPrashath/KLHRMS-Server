"""
Employee service — business logic for the employee list.

Queries Members joined with User, Role, and today's AttendanceRecord.
All queries are scoped by organizationId.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.microsoft_graph.graph_client import MicrosoftGraphClient
from app.integrations.microsoft_graph.token_manager import TokenManager
from app.models.microsoft_integration_setting import MicrosoftIntegrationSetting
from app.models.role import Role
from app.modules.employee.schema import (
    AttendanceTodayResponse,
    EmployeeDeletePreview,
    EmployeeDeleteResponse,
    EmployeeDeactivateResponse,
    EmployeeListFilters,
    EmployeeListItem,
    EmployeeListResponse,
    RoleBriefResponse,
)
from app.models.recruitment import StageEventParticipant, HiringTeamMember, StageEvent, EventStatus

logger = logging.getLogger("klhrms.employee.service")


async def list_employees(
    organization_id: str,
    filters: EmployeeListFilters,
    db: AsyncSession,
) -> EmployeeListResponse:
    # ── Resolve Microsoft Graph credentials ──────────────────────────────────
    tenant_id = ""
    client_id = ""
    client_secret = ""

    settings_result = await db.execute(
        select(MicrosoftIntegrationSetting).where(
            MicrosoftIntegrationSetting.organization_id == UUID(organization_id),
            MicrosoftIntegrationSetting.is_enabled.is_(True),
        )
    )
    settings = settings_result.scalar_one_or_none()
    if settings:
        tenant_id = settings.tenant_id
        client_id = settings.client_id
        client_secret = settings.client_secret_ciphertext
    else:
        from app.shared.config import get_settings as get_app_settings
        env = get_app_settings()
        if env.azure_tenant_id and env.azure_client_id and env.azure_client_secret:
            tenant_id = env.azure_tenant_id
            client_id = env.azure_client_id
            client_secret = env.azure_client_secret

    items: list[EmployeeListItem] = []

    if not (tenant_id and client_id and client_secret):
        return EmployeeListResponse(items=[], total=0, page=1, page_size=filters.page_size, total_pages=0)

    # ── Fetch users live from Microsoft Graph API ────────────────────────────
    page_size = max(1, min(100, filters.page_size))
    page = max(1, filters.page)

    try:
        logger.info("Fetching Microsoft Graph users for org %s", organization_id)
        tm = TokenManager(tenant_id, client_id, client_secret)
        client = MicrosoftGraphClient(tm)
        graph_users = await client.get_users()
        logger.info("Fetched %d users from Microsoft Graph", len(graph_users))
    except Exception as e:
        logger.error("Failed to fetch Microsoft Graph users: %s", e)
        return EmployeeListResponse(items=[], total=0, page=1, page_size=page_size, total_pages=0)

    # ── Look up default "Employee" role for this org ─────────────────────────
    default_role: RoleBriefResponse | None = None
    role_result = await db.execute(
        select(Role)
        .where(Role.organizationId == organization_id)
        .order_by(Role.name.asc())
    )
    all_roles: list[Role] = list(role_result.scalars().all())
    for r in all_roles:
        if r.name.lower() == "employee":
            default_role = RoleBriefResponse(id=r.id, name=r.name)
            break
    if default_role is None and all_roles:
        default_role = RoleBriefResponse(id=all_roles[0].id, name=all_roles[0].name)

    # ── Search filter (client-side on fetched users) ─────────────────────────
    filtered = graph_users
    if filters.search:
        term = filters.search.strip().lower()
        filtered = [
            u for u in filtered
            if term in (u.display_name or "").lower()
            or term in (u.email or "").lower()
            or term in (u.user_principal_name or "").lower()
        ]

    total = len(filtered)
    total_pages = max(1, -(-total // page_size))

    # ── Paginate ─────────────────────────────────────────────────────────────
    offset = (page - 1) * page_size
    page_users = filtered[offset:offset + page_size]

    # ── Build response items ─────────────────────────────────────────────────
    for gu in page_users:
        items.append(
            EmployeeListItem(
                member_id=gu.graph_id,
                user_id='',
                name=gu.display_name or gu.email or gu.user_principal_name or 'Unknown',
                email=gu.email or gu.user_principal_name or '',
                image=None,
                role=default_role,
                joined_at='',
                attendance_today=AttendanceTodayResponse(status='NO_RECORD'),
                microsoft_synced=True,
            )
        )

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


async def deactivate_employee(
    organization_id: str,
    member_id: str,
    db: AsyncSession,
) -> EmployeeDeactivateResponse:
    """Set a member's status to INACTIVE (soft-delete)."""

    member = await db.get(Member, member_id)
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
