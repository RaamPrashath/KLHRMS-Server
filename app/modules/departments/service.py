from __future__ import annotations

from fastapi import HTTPException
import re
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.department import Department
from app.models.member import Member
from app.models.project import Project
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User
from app.modules.departments.schema import (
    DepartmentListResponse,
    DepartmentMetaResponse,
    DepartmentProjectSummary,
    DepartmentSummary,
    DepartmentUpsertRequest,
    LookupOption,
    TeamMemberAssignRequest,
    TeamMemberSummary,
    TeamSummary,
    TeamUpsertRequest,
)
from app.shared.deps.organization_member import MemberContext


def _display_employee_name(name: str | None, email: str | None, fallback: str) -> str:
    normalized_name = (name or "").strip()
    normalized_email = (email or "").strip()

    if normalized_name and normalized_name.lower() != normalized_email.lower():
        return normalized_name

    if normalized_email:
        local_part = normalized_email.split("@", 1)[0].strip()
        if local_part:
            prettified = re.sub(r"[._-]+", " ", local_part).strip()
            if prettified:
                return " ".join(part.capitalize() for part in prettified.split())
        return normalized_email

    return fallback


def _member_name(member: Member | None) -> str | None:
    if member is None or member.user is None:
        return None
    return _display_employee_name(member.user.name, member.user.email, member.id)


def _department_to_summary(department: Department, member_id: str | None = None) -> DepartmentSummary:
    teams = [
        _team_to_summary(team)
        for team in department.teams
        if team.status == "ACTIVE" and (member_id is None or any(item.memberId == member_id for item in team.members))
    ]
    member_ids = {member.memberId for team in teams for member in team.members}
    return DepartmentSummary(
        id=department.id,
        name=department.name,
        parentDepartmentId=department.parentDepartmentId,
        headMemberId=department.headMemberId,
        headMemberName=_member_name(getattr(department, "head_member", None)),
        status=department.status,
        teamCount=len(teams),
        memberCount=len(member_ids),
        projectCount=sum(team.projectCount for team in teams),
        teams=teams,
        createdAt=department.createdAt,
        updatedAt=department.updatedAt,
    )


def _team_to_summary(team: Team) -> TeamSummary:
    members = [
        TeamMemberSummary(
            id=item.id,
            memberId=item.memberId,
            name=item.member.user.name if item.member and item.member.user else None,
            email=item.member.user.email if item.member and item.member.user else None,
            role=item.role,
        )
        for item in team.members
    ]
    projects = [
        DepartmentProjectSummary(
            id=project.id,
            name=project.name,
            status=project.status,
            billable=project.billable,
            memberCount=len(project.members),
        )
        for project in team.projects
        if project.deletedAt is None
    ]
    return TeamSummary(
        id=team.id,
        departmentId=team.departmentId,
        name=team.name,
        description=team.description,
        leadMemberId=team.leadMemberId,
        leadMemberName=_member_name(team.lead_member),
        status=team.status,
        memberCount=len(members),
        projectCount=len(projects),
        members=members,
        projects=projects,
        createdAt=team.createdAt,
        updatedAt=team.updatedAt,
    )


async def _validate_member(db: AsyncSession, ctx: MemberContext, member_id: str | None) -> None:
    if not member_id:
        return
    result = await db.execute(select(Member.id).where(Member.id == member_id, Member.organizationId == ctx.organization.id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Employee not found")


async def _validate_department(db: AsyncSession, ctx: MemberContext, department_id: str) -> Department:
    result = await db.execute(
        select(Department).where(
            Department.id == department_id,
            Department.organizationId == ctx.organization.id,
            Department.status == "ACTIVE",
        )
    )
    department = result.scalar_one_or_none()
    if department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    return department


async def list_departments(
    db: AsyncSession,
    ctx: MemberContext,
    search: str | None = None,
) -> DepartmentListResponse:
    scope = getattr(ctx, "scope", "organization")
    query = select(Department).where(Department.organizationId == ctx.organization.id, Department.status == "ACTIVE")
    if search:
        term = f"%{search.strip()}%"
        query = query.where(Department.name.ilike(term))
    if scope == "self":
        query = (
            query.join(Team, Team.departmentId == Department.id)
            .join(TeamMember, TeamMember.teamId == Team.id)
            .where(TeamMember.memberId == ctx.member.id, Team.status == "ACTIVE")
            .distinct()
        )

    total_result = await db.execute(select(func.count()).select_from(query.order_by(None).subquery()))
    result = await db.execute(
        query.options(joinedload(Department.teams).joinedload(Team.members).joinedload(TeamMember.member).joinedload(Member.user))
        .options(joinedload(Department.head_member).joinedload(Member.user))
        .options(joinedload(Department.teams).joinedload(Team.lead_member).joinedload(Member.user))
        .options(joinedload(Department.teams).joinedload(Team.projects).joinedload(Project.members))
        .order_by(Department.name.asc())
    )
    departments = result.unique().scalars().all()
    visible_member_id = ctx.member.id if scope == "self" else None
    return DepartmentListResponse(
        items=[_department_to_summary(item, visible_member_id) for item in departments],
        total=total_result.scalar_one(),
    )


async def upsert_department(
    db: AsyncSession,
    ctx: MemberContext,
    payload: DepartmentUpsertRequest,
    department_id: str | None = None,
) -> DepartmentSummary:
    department: Department | None = None
    if department_id:
        department = await _validate_department(db, ctx, department_id)
    else:
        department = Department(organizationId=ctx.organization.id)
        db.add(department)

    await _validate_member(db, ctx, payload.headMemberId)
    if payload.parentDepartmentId:
        await _validate_department(db, ctx, payload.parentDepartmentId)

    department.name = payload.name.strip()
    department.headMemberId = payload.headMemberId
    department.parentDepartmentId = payload.parentDepartmentId
    department.status = payload.status
    await db.commit()
    departments = await list_departments(db, ctx)
    return next(item for item in departments.items if item.id == department.id)


async def deactivate_department(db: AsyncSession, ctx: MemberContext, department_id: str) -> None:
    department = await _validate_department(db, ctx, department_id)
    department.status = "INACTIVE"
    teams_result = await db.execute(select(Team).where(Team.departmentId == department_id, Team.organizationId == ctx.organization.id))
    for team in teams_result.scalars().all():
        team.status = "INACTIVE"
    await db.commit()


async def upsert_team(
    db: AsyncSession,
    ctx: MemberContext,
    department_id: str,
    payload: TeamUpsertRequest,
    team_id: str | None = None,
) -> DepartmentSummary:
    await _validate_department(db, ctx, department_id)
    await _validate_member(db, ctx, payload.leadMemberId)
    team: Team | None = None
    if team_id:
        result = await db.execute(
            select(Team).where(
                Team.id == team_id,
                Team.departmentId == department_id,
                Team.organizationId == ctx.organization.id,
                Team.status == "ACTIVE",
            )
        )
        team = result.scalar_one_or_none()
        if team is None:
            raise HTTPException(status_code=404, detail="Team not found")
    else:
        team = Team(organizationId=ctx.organization.id, departmentId=department_id)
        db.add(team)

    team.name = payload.name.strip()
    team.description = payload.description.strip() if payload.description else None
    team.leadMemberId = payload.leadMemberId
    team.status = payload.status
    await db.commit()
    departments = await list_departments(db, ctx)
    return next(item for item in departments.items if item.id == department_id)


async def deactivate_team(db: AsyncSession, ctx: MemberContext, department_id: str, team_id: str) -> DepartmentSummary:
    result = await db.execute(
        select(Team).where(
            Team.id == team_id,
            Team.departmentId == department_id,
            Team.organizationId == ctx.organization.id,
            Team.status == "ACTIVE",
        )
    )
    team = result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    team.status = "INACTIVE"
    projects_result = await db.execute(select(Project).where(Project.teamId == team_id, Project.organizationId == ctx.organization.id))
    for project in projects_result.scalars().all():
        project.teamId = None
    await db.commit()
    departments = await list_departments(db, ctx)
    return next(item for item in departments.items if item.id == department_id)


async def assign_team_member(
    db: AsyncSession,
    ctx: MemberContext,
    team_id: str,
    payload: TeamMemberAssignRequest,
) -> TeamSummary:
    team_result = await db.execute(select(Team).where(Team.id == team_id, Team.organizationId == ctx.organization.id, Team.status == "ACTIVE"))
    team = team_result.scalar_one_or_none()
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    await _validate_member(db, ctx, payload.memberId)
    existing_result = await db.execute(select(TeamMember).where(TeamMember.teamId == team_id, TeamMember.memberId == payload.memberId))
    existing = existing_result.scalar_one_or_none()
    if existing is None:
        db.add(TeamMember(teamId=team_id, memberId=payload.memberId, role=payload.role.strip() if payload.role else None))
    else:
        existing.role = payload.role.strip() if payload.role else None
    await db.commit()
    departments = await list_departments(db, ctx)
    return next(team_item for dept in departments.items for team_item in dept.teams if team_item.id == team_id)


async def remove_team_member(db: AsyncSession, ctx: MemberContext, team_id: str, member_id: str) -> TeamSummary:
    result = await db.execute(
        select(TeamMember)
        .join(Team, Team.id == TeamMember.teamId)
        .where(TeamMember.teamId == team_id, TeamMember.memberId == member_id, Team.organizationId == ctx.organization.id)
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=404, detail="Team member assignment not found")
    await db.delete(membership)
    await db.commit()
    departments = await list_departments(db, ctx)
    return next(team_item for dept in departments.items for team_item in dept.teams if team_item.id == team_id)


async def get_department_meta(db: AsyncSession, ctx: MemberContext) -> DepartmentMetaResponse:
    members_result = await db.execute(
        select(Member.id, User.name, User.email)
        .join(User, User.id == Member.userId)
        .where(Member.organizationId == ctx.organization.id)
        .order_by(User.name.asc().nullslast(), User.email.asc())
    )
    departments_result = await db.execute(
        select(Department.id, Department.name)
        .where(Department.organizationId == ctx.organization.id, Department.status == "ACTIVE")
        .order_by(Department.name.asc())
    )
    return DepartmentMetaResponse(
        members=[
            LookupOption(
                id=member_id,
                label=_display_employee_name(name, email, member_id),
                email=email,
            )
            for member_id, name, email in members_result.all()
        ],
        departments=[LookupOption(id=department_id, label=name) for department_id, name in departments_result.all()],
    )
