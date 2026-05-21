"""
Projects for Attendance — lightweight endpoint for work log project/task selection.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.project_task import ProjectTask
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/for-attendance")
async def list_projects_for_attendance(
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: AsyncSession = Depends(get_db),
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
