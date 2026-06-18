from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.department import Department
from app.models.member import Member
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.project_task import ProjectTask
from app.models.user import User
from app.modules.projects.schema import (
    ProjectCapacitySummary,
    ProjectDetailResponse,
    ProjectFilters,
    ProjectListResponse,
    ProjectLookupOption,
    ProjectMemberAssignBulkRequest,
    ProjectMemberAssignRequest,
    ProjectMemberSummary,
    ProjectMetaResponse,
    ProjectSummary,
    ProjectTaskCreateRequest,
    ProjectTaskSummary,
    ProjectUpsertRequest,
)
from app.shared.deps.organization_member import MemberContext


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _capacity_for(project: Project, allocated_hours: float) -> ProjectCapacitySummary:
    budgeted_hours = _to_float(project.budgetedHours)
    logged_hours = None
    remaining = None if budgeted_hours is None else round(budgeted_hours - allocated_hours, 2)
    warning = None
    if budgeted_hours is not None and allocated_hours > budgeted_hours:
        warning = "Allocated hours exceed the budgeted capacity."
    return ProjectCapacitySummary(
        budgetedHours=budgeted_hours,
        allocatedHours=round(allocated_hours, 2),
        loggedHours=logged_hours,
        remainingHours=remaining,
        warning=warning,
    )


async def list_projects(
    db: AsyncSession,
    ctx: MemberContext,
    filters: ProjectFilters,
) -> ProjectListResponse:
    scope = getattr(ctx, "scope", "organization")
    base_query = select(Project).where(
        Project.organizationId == ctx.organization.id,
        Project.deletedAt.is_(None),
    )
    if scope == "self":
        base_query = base_query.join(ProjectMember, ProjectMember.projectId == Project.id).where(
            ProjectMember.memberId == ctx.member.id
        )

    if filters.search:
        term = f"%{filters.search.strip()}%"
        base_query = base_query.where(or_(Project.name.ilike(term), Project.clientName.ilike(term)))
    if filters.status:
        base_query = base_query.where(Project.status == filters.status)
    if filters.billable is not None:
        base_query = base_query.where(Project.billable == filters.billable)

    total_result = await db.execute(select(func.count()).select_from(base_query.order_by(None).subquery()))
    total = total_result.scalar_one()

    query = (
        base_query.options(joinedload(Project.members).joinedload(ProjectMember.member).joinedload(Member.user))
        .options(joinedload(Project.tasks))
        .order_by(Project.updatedAt.desc(), Project.createdAt.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    )
    rows = await db.execute(query)
    projects = rows.unique().scalars().all()

    items = []
    for project in projects:
        allocated_hours = sum(float(member.allocatedHours or 0) for member in project.members)
        items.append(
            ProjectSummary(
                id=project.id,
                name=project.name,
                clientName=project.clientName,
                budget=_to_float(project.budget),
                budgetedHours=_to_float(project.budgetedHours),
                startDate=project.startDate,
                endDate=project.endDate,
                status=project.status,
                billable=project.billable,
                memberCount=len(project.members),
                taskCount=len(project.tasks),
                allocatedHours=round(allocated_hours, 2),
                capacity=_capacity_for(project, allocated_hours),
                createdAt=project.createdAt,
                updatedAt=project.updatedAt,
            )
        )

    return ProjectListResponse(items=items, total=total, page=filters.page, page_size=filters.page_size)


async def get_project(db: AsyncSession, ctx: MemberContext, project_id: str) -> ProjectDetailResponse:
    scope = getattr(ctx, "scope", "organization")
    result = await db.execute(
        select(Project)
        .where(
            Project.id == project_id,
            Project.organizationId == ctx.organization.id,
            Project.deletedAt.is_(None),
        )
        .options(joinedload(Project.members).joinedload(ProjectMember.member).joinedload(Member.user))
        .options(joinedload(Project.tasks))
    )
    project = result.unique().scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if scope == "self" and all(member.memberId != ctx.member.id for member in project.members):
        raise HTTPException(status_code=404, detail="Project not found")

    allocated_hours = sum(float(member.allocatedHours or 0) for member in project.members)
    members = [
        ProjectMemberSummary(
            id=member.id,
            memberId=member.memberId,
            name=member.member.user.name if member.member and member.member.user else None,
            email=member.member.user.email if member.member and member.member.user else None,
            role=member.role,
            allocatedHours=_to_float(member.allocatedHours),
        )
        for member in project.members
    ]
    tasks = [
        ProjectTaskSummary(
            id=task.id,
            name=task.name,
            createdAt=task.createdAt,
        )
        for task in sorted(project.tasks, key=lambda item: item.createdAt, reverse=True)
    ]

    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        clientName=project.clientName,
        budget=_to_float(project.budget),
        budgetedHours=_to_float(project.budgetedHours),
        startDate=project.startDate,
        endDate=project.endDate,
        status=project.status,
        billable=project.billable,
        memberCount=len(project.members),
        taskCount=len(project.tasks),
        allocatedHours=round(allocated_hours, 2),
        capacity=_capacity_for(project, allocated_hours),
        createdAt=project.createdAt,
        updatedAt=project.updatedAt,
        description=project.description,
        members=members,
        tasks=tasks,
    )


async def upsert_project(
    db: AsyncSession,
    ctx: MemberContext,
    payload: ProjectUpsertRequest,
    project_id: str | None = None,
) -> ProjectDetailResponse:
    project: Project | None = None
    if project_id is not None:
        existing = await db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organizationId == ctx.organization.id,
                Project.deletedAt.is_(None),
            )
        )
        project = existing.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
    else:
        project = Project(organizationId=ctx.organization.id)
        db.add(project)

    project.name = payload.name.strip()
    project.clientName = payload.clientName.strip() if payload.clientName else None
    project.budget = payload.budget
    project.budgetedHours = payload.budgetedHours
    project.startDate = payload.startDate
    project.endDate = payload.endDate
    project.status = payload.status
    project.billable = payload.billable
    project.description = payload.description.strip() if payload.description else None

    await db.commit()
    await db.refresh(project)
    return await get_project(db, ctx, project.id)


async def delete_project(db: AsyncSession, ctx: MemberContext, project_id: str) -> None:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organizationId == ctx.organization.id,
            Project.deletedAt.is_(None),
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    project.deletedAt = datetime.now(UTC)
    await db.commit()


async def add_project_member(
    db: AsyncSession,
    ctx: MemberContext,
    project_id: str,
    payload: ProjectMemberAssignRequest,
) -> ProjectDetailResponse:
    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organizationId == ctx.organization.id,
            Project.deletedAt.is_(None),
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    member_result = await db.execute(
        select(Member).where(Member.id == payload.memberId, Member.organizationId == ctx.organization.id)
    )
    member = member_result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    existing_result = await db.execute(
        select(ProjectMember).where(ProjectMember.projectId == project_id, ProjectMember.memberId == payload.memberId)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is None:
        db.add(
            ProjectMember(
                projectId=project_id,
                memberId=payload.memberId,
                role=payload.role.strip() if payload.role else None,
                allocatedHours=payload.allocatedHours,
            )
        )
    else:
        existing.role = payload.role.strip() if payload.role else None
        existing.allocatedHours = payload.allocatedHours

    await db.commit()
    return await get_project(db, ctx, project_id)


async def bulk_assign_project_members(
    db: AsyncSession,
    ctx: MemberContext,
    project_id: str,
    payload: ProjectMemberAssignBulkRequest,
) -> ProjectDetailResponse:
    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organizationId == ctx.organization.id,
            Project.deletedAt.is_(None),
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    for member_id in payload.memberIds:
        member_result = await db.execute(
            select(Member).where(Member.id == member_id, Member.organizationId == ctx.organization.id)
        )
        member = member_result.scalar_one_or_none()
        if member is None:
            continue

        existing_result = await db.execute(
            select(ProjectMember).where(
                ProjectMember.projectId == project_id,
                ProjectMember.memberId == member_id,
            )
        )
        if existing_result.scalar_one_or_none() is None:
            db.add(ProjectMember(projectId=project_id, memberId=member_id))

    await db.commit()
    return await get_project(db, ctx, project_id)


async def remove_project_member(    db: AsyncSession,
    ctx: MemberContext,
    project_id: str,
    member_id: str,
) -> ProjectDetailResponse:
    result = await db.execute(
        select(ProjectMember)
        .join(Project, Project.id == ProjectMember.projectId)
        .where(
            ProjectMember.projectId == project_id,
            ProjectMember.memberId == member_id,
            Project.organizationId == ctx.organization.id,
            Project.deletedAt.is_(None),
        )
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Project member assignment not found")

    await db.delete(assignment)
    await db.commit()
    return await get_project(db, ctx, project_id)


async def list_project_tasks(db: AsyncSession, ctx: MemberContext, project_id: str) -> list[ProjectTaskSummary]:
    project = await get_project(db, ctx, project_id)
    return project.tasks


async def create_project_task(
    db: AsyncSession,
    ctx: MemberContext,
    project_id: str,
    payload: ProjectTaskCreateRequest,
) -> list[ProjectTaskSummary]:
    project_result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.organizationId == ctx.organization.id,
            Project.deletedAt.is_(None),
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    db.add(
        ProjectTask(
            projectId=project_id,
            name=payload.name.strip(),
        )
    )
    await db.commit()
    return await list_project_tasks(db, ctx, project_id)


async def get_project_meta(db: AsyncSession, ctx: MemberContext) -> ProjectMetaResponse:
    scope = getattr(ctx, "scope", "organization")
    members_query = (
        select(Member.id, User.name, User.email)
        .join(User, User.id == Member.userId)
        .where(Member.organizationId == ctx.organization.id)
        .order_by(User.name.asc().nullslast(), User.email.asc())
    )
    if scope == "self":
        members_query = members_query.where(Member.id == ctx.member.id)
    else:
        members_query = members_query.where(Member.status == "ACTIVE")  # status: ACTIVE only
    members_result = await db.execute(members_query)
    departments_result = await db.execute(
        select(Department.id, Department.name)
        .where(Department.organizationId == ctx.organization.id, Department.status == "ACTIVE")
        .order_by(Department.name.asc())
    )
    members = [
        ProjectLookupOption(id=member_id, label=name or email or member_id, email=email)
        for member_id, name, email in members_result.all()
    ]
    departments = [ProjectLookupOption(id=dept_id, label=name) for dept_id, name in departments_result.all()]
    return ProjectMetaResponse(members=members, departments=departments)


async def list_projects_for_attendance(
    db: AsyncSession,
    ctx: MemberContext,
):
    """
    Return active projects with their tasks for attendance work log selection.
    Only returns projects that are ACTIVE and not deleted.
    """
    # Fetch active projects the employee is assigned to
    projects_result = await db.execute(
        select(Project)
        .join(ProjectMember, ProjectMember.projectId == Project.id)
        .where(
            Project.organizationId == ctx.organization.id,
            Project.status == "ACTIVE",
            Project.deletedAt.is_(None),
            ProjectMember.memberId == ctx.member.id,
        )
        .order_by(Project.name)
    )
    projects = projects_result.scalars().all()

    if not projects:
        return []

    # Fetch all tasks for these projects
    project_ids = [p.id for p in projects]
    tasks_result = await db.execute(
        select(ProjectTask)
        .where(ProjectTask.projectId.in_(project_ids))
        .order_by(ProjectTask.name)
    )
    tasks = tasks_result.scalars().all()

    # Group tasks by project
    tasks_by_project: dict[str, list[dict]] = {}
    for task in tasks:
        if task.projectId not in tasks_by_project:
            tasks_by_project[task.projectId] = []
        tasks_by_project[task.projectId].append({
            "id": task.id,
            "name": task.name,
        })

    # Build response
    return [
        {
            "id": project.id,
            "name": project.name,
            "tasks": tasks_by_project.get(project.id, []),
        }
        for project in projects
    ]
