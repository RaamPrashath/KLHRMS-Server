from __future__ import annotations

from fastapi import HTTPException
import re
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.department import Department
from app.models.department_member import DepartmentMember
from app.models.member import Member
from app.models.user import User
from app.modules.departments.schema import (
    DepartmentMemberSummary,
    DepartmentListResponse,
    DepartmentMetaResponse,
    DepartmentProjectSummary,
    DepartmentSummary,
    DepartmentUpsertRequest,
    LookupOption,
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
    members = [
        DepartmentMemberSummary(
            id=item.id,
            memberId=item.memberId,
            name=item.member.user.name if item.member and item.member.user else None,
            email=item.member.user.email if item.member and item.member.user else None,
        )
        for item in department.members
        if member_id is None or item.memberId == member_id
    ]
    projects = [
        DepartmentProjectSummary(
            id=project.id,
            name=project.name,
            status=project.status,
            billable=project.billable,
            memberCount=len(project.members),
        )
        for project in getattr(department, "projects", [])
        if project.deletedAt is None
    ]
    return DepartmentSummary(
        id=department.id,
        name=department.name,
        parentDepartmentId=department.parentDepartmentId,
        headMemberId=department.headMemberId,
        headMemberName=_member_name(getattr(department, "head_member", None)),
        status=department.status,
        memberCount=len(members),
        projectCount=len(projects),
        members=members,
        projects=projects,
        createdAt=department.createdAt,
        updatedAt=department.updatedAt,
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
            query.join(DepartmentMember, DepartmentMember.departmentId == Department.id)
            .where(DepartmentMember.memberId == ctx.member.id)
            .distinct()
        )

    total_result = await db.execute(select(func.count()).select_from(query.order_by(None).subquery()))
    result = await db.execute(
        query.options(joinedload(Department.members).joinedload(DepartmentMember.member).joinedload(Member.user))
        .options(joinedload(Department.head_member).joinedload(Member.user))
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
    await db.commit()


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
