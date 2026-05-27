from __future__ import annotations

from datetime import datetime, timezone
from math import ceil

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.access_control_assignment import AccessControlAssignment
from app.models.access_control_log import AccessControlLog
from app.models.member import Member
from app.models.asset import Asset
from app.models.user import User
from app.shared.deps.organization_member import MemberContext


_UTC = timezone.utc


async def list_logs(
    db: AsyncSession,
    ctx: MemberContext,
    page: int = 1,
    page_size: int = 20,
    employee_member_id: str | None = None,
    access_point: str | None = None,
    status: str | None = None,
    direction: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    query = (
        select(AccessControlLog)
        .where(
            AccessControlLog.organizationId == ctx.organization.id,
        )
        .options(
            joinedload(AccessControlLog.employee).joinedload(Member.user),
            joinedload(AccessControlLog.asset),
        )
    )

    if employee_member_id:
        query = query.where(AccessControlLog.employeeMemberId == employee_member_id)
    if access_point:
        query = query.where(AccessControlLog.accessPoint == access_point)
    if status:
        query = query.where(AccessControlLog.status == status)
    if direction:
        query = query.where(AccessControlLog.direction == direction)
    if date_from:
        query = query.where(AccessControlLog.enteredAt >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(AccessControlLog.enteredAt <= datetime.fromisoformat(date_to))

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(AccessControlLog.enteredAt.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    logs = result.unique().scalars().all()

    items = []
    for log in logs:
        employee_name = log.employee.user.name if log.employee and log.employee.user else None
        employee_email = log.employee.user.email if log.employee and log.employee.user else None
        asset_name = log.asset.name if log.asset else None
        asset_code = log.asset.assetCode if log.asset else None
        items.append({
            "id": log.id,
            "employeeMemberId": log.employeeMemberId,
            "assetId": log.assetId,
            "accessPoint": log.accessPoint,
            "entryMethod": log.entryMethod,
            "status": log.status,
            "direction": log.direction,
            "enteredAt": log.enteredAt,
            "isActive": log.isActive,
            "notes": log.notes,
            "createdAt": log.createdAt,
            "employeeName": employee_name,
            "employeeEmail": employee_email,
            "assetName": asset_name,
            "assetCode": asset_code,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def get_log_summary(
    db: AsyncSession,
    ctx: MemberContext,
) -> dict:
    today_start = datetime.now(_UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    today_count = await db.execute(
        select(func.count(AccessControlLog.id)).where(
            AccessControlLog.organizationId == ctx.organization.id,
            AccessControlLog.enteredAt >= today_start,
        )
    )
    total_entries_today = today_count.scalar_one()

    granted_count = await db.execute(
        select(func.count(AccessControlLog.id)).where(
            AccessControlLog.organizationId == ctx.organization.id,
            AccessControlLog.enteredAt >= today_start,
            AccessControlLog.status == "GRANTED",
        )
    )
    granted_today = granted_count.scalar_one()

    denied_count = await db.execute(
        select(func.count(AccessControlLog.id)).where(
            AccessControlLog.organizationId == ctx.organization.id,
            AccessControlLog.enteredAt >= today_start,
            AccessControlLog.status == "DENIED",
        )
    )
    denied_today = denied_count.scalar_one()

    active_assignments_count = await db.execute(
        select(func.count(AccessControlAssignment.id)).where(
            AccessControlAssignment.organizationId == ctx.organization.id,
            AccessControlAssignment.status == "ACTIVE",
        )
    )
    active_assignments = active_assignments_count.scalar_one()

    unique_employees = await db.execute(
        select(func.count(func.distinct(AccessControlLog.employeeMemberId))).where(
            AccessControlLog.organizationId == ctx.organization.id,
            AccessControlLog.enteredAt >= today_start,
        )
    )

    return {
        "totalEntriesToday": total_entries_today,
        "grantedToday": granted_today,
        "deniedToday": denied_today,
        "activeAssignments": active_assignments,
        "uniqueEmployeesToday": unique_employees.scalar_one(),
    }


async def create_log(
    db: AsyncSession,
    ctx: MemberContext,
    payload: dict,
) -> dict:
    log = AccessControlLog(
        organizationId=ctx.organization.id,
        employeeMemberId=payload["employeeMemberId"],
        assetId=payload.get("assetId"),
        accessPoint=payload["accessPoint"],
        entryMethod=payload["entryMethod"],
        status=payload["status"],
        direction=payload["direction"],
        enteredAt=payload["enteredAt"],
        isActive=payload.get("isActive", True),
        notes=payload.get("notes"),
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return {"id": log.id, "message": "Access log created"}


async def update_log(
    db: AsyncSession,
    ctx: MemberContext,
    log_id: str,
    payload: dict,
) -> dict:
    result = await db.execute(
        select(AccessControlLog).where(
            AccessControlLog.id == log_id,
            AccessControlLog.organizationId == ctx.organization.id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Access log not found")

    if "isActive" in payload:
        log.isActive = payload["isActive"]
    if "notes" in payload:
        log.notes = payload["notes"]

    await db.commit()
    await db.refresh(log)
    return {"id": log.id, "message": "Access log updated"}


async def bulk_import_logs(
    db: AsyncSession,
    ctx: MemberContext,
    logs: list[dict],
) -> dict:
    imported = 0
    for entry in logs:
        log = AccessControlLog(
            organizationId=ctx.organization.id,
            employeeMemberId=entry["employeeMemberId"],
            assetId=entry.get("assetId"),
            accessPoint=entry["accessPoint"],
            entryMethod=entry["entryMethod"],
            status=entry["status"],
            direction=entry["direction"],
            enteredAt=entry["enteredAt"],
            isActive=entry.get("isActive", True),
            notes=entry.get("notes"),
        )
        db.add(log)
        imported += 1

    await db.commit()
    return {"imported": imported, "message": f"{imported} access logs imported"}


async def list_assignments(
    db: AsyncSession,
    ctx: MemberContext,
    page: int = 1,
    page_size: int = 20,
    employee_member_id: str | None = None,
    access_point: str | None = None,
    status: str | None = None,
) -> dict:
    query = (
        select(AccessControlAssignment)
        .where(AccessControlAssignment.organizationId == ctx.organization.id)
        .options(
            joinedload(AccessControlAssignment.employee).joinedload(Member.user),
            joinedload(AccessControlAssignment.grantedBy).joinedload(Member.user),
        )
    )

    if employee_member_id:
        query = query.where(AccessControlAssignment.employeeMemberId == employee_member_id)
    if access_point:
        query = query.where(AccessControlAssignment.accessPoint == access_point)
    if status:
        query = query.where(AccessControlAssignment.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(AccessControlAssignment.createdAt.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    assignments = result.unique().scalars().all()

    items = []
    for a in assignments:
        employee_name = a.employee.user.name if a.employee and a.employee.user else None
        employee_email = a.employee.user.email if a.employee and a.employee.user else None
        granted_by_name = a.grantedBy.user.name if a.grantedBy and a.grantedBy.user else None
        items.append({
            "id": a.id,
            "employeeMemberId": a.employeeMemberId,
            "accessPoint": a.accessPoint,
            "status": a.status,
            "grantedByMemberId": a.grantedByMemberId,
            "grantedAt": a.grantedAt,
            "revokedAt": a.revokedAt,
            "createdAt": a.createdAt,
            "updatedAt": a.updatedAt,
            "employeeName": employee_name,
            "employeeEmail": employee_email,
            "grantedByName": granted_by_name,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


async def create_assignment(
    db: AsyncSession,
    ctx: MemberContext,
    payload: dict,
) -> dict:
    existing = await db.execute(
        select(AccessControlAssignment).where(
            AccessControlAssignment.organizationId == ctx.organization.id,
            AccessControlAssignment.employeeMemberId == payload["employeeMemberId"],
            AccessControlAssignment.accessPoint == payload["accessPoint"],
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Assignment already exists for this employee and access point")

    assignment = AccessControlAssignment(
        organizationId=ctx.organization.id,
        employeeMemberId=payload["employeeMemberId"],
        accessPoint=payload["accessPoint"],
        status=payload.get("status", "ACTIVE"),
        grantedByMemberId=ctx.member.id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return {"id": assignment.id, "message": "Access assignment created"}


async def update_assignment(
    db: AsyncSession,
    ctx: MemberContext,
    assignment_id: str,
    payload: dict,
) -> dict:
    result = await db.execute(
        select(AccessControlAssignment).where(
            AccessControlAssignment.id == assignment_id,
            AccessControlAssignment.organizationId == ctx.organization.id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if "status" in payload:
        assignment.status = payload["status"]
        if payload["status"] == "DISABLED":
            assignment.revokedAt = datetime.now(_UTC)
    if payload.get("revokedAt"):
        assignment.revokedAt = payload["revokedAt"]

    await db.commit()
    await db.refresh(assignment)
    return {"id": assignment.id, "status": assignment.status, "message": "Assignment updated"}
