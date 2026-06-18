"""Core business logic for the leave module."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, joinedload

from app.models.base import generate_uuid
from app.models.leave import Holiday, LeaveBalance, LeaveRequest, LeaveType
from app.models.member import Member
from app.modules.leave.schema import LeaveBalanceFilters, LeaveCalendarFilters, LeaveRequestFilters
from app.shared.utils.enums import LeaveRequestStatus


@dataclass
class LeaveBalanceRow:
    """Synthetic balance row — covers leave types with no existing balance record."""
    id: str
    organizationId: str
    memberId: str
    leaveTypeId: str
    year: int
    allocated: float
    used: float
    remaining: float
    carriedForward: float
    lapsed: float
    createdAt: dt.datetime
    updatedAt: dt.datetime
    member: Member
    leave_type: LeaveType


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _year_bounds(year: int) -> tuple[dt.date, dt.date]:
    start = dt.date(year, 1, 1)
    end = dt.date(year + 1, 1, 1)
    return start, end


async def _get_approved_leave_days(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    leave_type_id: str,
    year: int,
) -> float:
    year_start, next_year_start = _year_bounds(year)
    result = await db.execute(
        select(func.coalesce(func.sum(LeaveRequest.days), 0.0)).where(
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.memberId == member_id,
            LeaveRequest.leaveTypeId == leave_type_id,
            LeaveRequest.status == LeaveRequestStatus.APPROVED.value,
            LeaveRequest.deletedAt.is_(None),
            LeaveRequest.startDate >= year_start,
            LeaveRequest.startDate < next_year_start,
        )
    )
    return float(result.scalar_one() or 0.0)


async def resolve_target_member(db: AsyncSession, organization_id: str, member_id: str) -> Member:
    result = await db.execute(
        select(Member)
        .options(joinedload(Member.user), joinedload(Member.role))
        .where(
            Member.id == member_id,
            Member.organizationId == organization_id,
        )
    )
    member = result.unique().scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


async def get_leave_type_or_404(db: AsyncSession, organization_id: str, leave_type_id: str) -> LeaveType:
    result = await db.execute(
        select(LeaveType).where(
            LeaveType.id == leave_type_id,
            LeaveType.organizationId == organization_id,
            LeaveType.deletedAt.is_(None),
        )
    )
    leave_type = result.scalar_one_or_none()
    if leave_type is None:
        raise HTTPException(status_code=404, detail="Leave type not found")
    return leave_type


async def get_holiday_or_404(db: AsyncSession, organization_id: str, holiday_id: str) -> Holiday:
    result = await db.execute(
        select(Holiday).where(
            Holiday.id == holiday_id,
            Holiday.organizationId == organization_id,
            Holiday.deletedAt.is_(None),
        )
    )
    holiday = result.scalar_one_or_none()
    if holiday is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    return holiday


async def get_leave_request_or_404(db: AsyncSession, organization_id: str, leave_request_id: str) -> LeaveRequest:
    result = await db.execute(
        select(LeaveRequest)
        .options(
            joinedload(LeaveRequest.member).joinedload(Member.user),
            joinedload(LeaveRequest.approved_by).joinedload(Member.user),
            joinedload(LeaveRequest.leave_type),
        )
        .where(
            LeaveRequest.id == leave_request_id,
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.deletedAt.is_(None),
        )
    )
    leave_request = result.unique().scalar_one_or_none()
    if leave_request is None:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return leave_request


async def _ensure_leave_type_name_available(
    db: AsyncSession,
    organization_id: str,
    name: str,
    exclude_id: str | None = None,
) -> None:
    query = select(LeaveType).where(
        LeaveType.organizationId == organization_id,
        LeaveType.deletedAt.is_(None),
        func.lower(LeaveType.name) == name.strip().lower(),
    )
    if exclude_id is not None:
        query = query.where(LeaveType.id != exclude_id)
    result = await db.execute(query)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A leave type with this name already exists")


async def list_leave_types(db: AsyncSession, organization_id: str) -> list[LeaveType]:
    result = await db.execute(
        select(LeaveType).where(
            LeaveType.organizationId == organization_id,
            LeaveType.deletedAt.is_(None),
        )
        .order_by(LeaveType.name.asc())
    )
    return result.scalars().all()


async def create_leave_type(
    db: AsyncSession,
    organization_id: str,
    *,
    name: str,
    quota: float,
    carry_forward: bool,
    is_paid: bool,
    color: str | None,
) -> LeaveType:
    normalized_name = name.strip()
    now = _utcnow()
    result = await db.execute(
        select(LeaveType).where(
            LeaveType.organizationId == organization_id,
            func.lower(LeaveType.name) == normalized_name.lower(),
        )
    )
    matching_leave_types = list(result.scalars().all())
    existing_leave_type = next(
        (leave_type for leave_type in matching_leave_types if leave_type.deletedAt is None),
        matching_leave_types[0] if matching_leave_types else None,
    )
    if existing_leave_type is not None:
        existing_leave_type.name = normalized_name
        existing_leave_type.quota = quota
        existing_leave_type.carryForward = carry_forward
        existing_leave_type.isPaid = is_paid
        existing_leave_type.color = color
        existing_leave_type.deletedAt = None
        existing_leave_type.updatedAt = now
        try:
            await db.commit()
            await db.refresh(existing_leave_type)
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(status_code=409, detail="A leave type with this name already exists") from exc
        return existing_leave_type

    leave_type = LeaveType(
        id=generate_uuid(),
        organizationId=organization_id,
        name=normalized_name,
        quota=quota,
        carryForward=carry_forward,
        isPaid=is_paid,
        color=color,
        createdAt=now,
        updatedAt=now,
    )
    db.add(leave_type)

    try:
        await db.commit()
        await db.refresh(leave_type)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A leave type with this name already exists") from exc
    return leave_type


async def update_leave_type(
    db: AsyncSession,
    organization_id: str,
    leave_type_id: str,
    *,
    name: str,
    quota: float,
    carry_forward: bool,
    is_paid: bool,
    color: str | None,
) -> LeaveType:
    leave_type = await get_leave_type_or_404(db, organization_id, leave_type_id)
    await _ensure_leave_type_name_available(db, organization_id, name, exclude_id=leave_type_id)

    now = _utcnow()
    leave_type.name = name.strip()
    leave_type.quota = quota
    leave_type.carryForward = carry_forward
    leave_type.isPaid = is_paid
    leave_type.color = color
    leave_type.updatedAt = now

    try:
        await db.commit()
        await db.refresh(leave_type)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Failed to update leave type") from exc
    return leave_type


async def list_holidays(
    db: AsyncSession,
    organization_id: str,
    *,
    year: int | None = None,
    month: int | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Holiday], int]:
    query = select(Holiday).where(
        Holiday.organizationId == organization_id,
        Holiday.deletedAt.is_(None),
        Holiday.isHoliday.is_(True),
    )
    if year is not None:
        query = query.where(func.extract("year", Holiday.holidayDate) == year)
    if month is not None:
        query = query.where(func.extract("month", Holiday.holidayDate) == month)
    if search is not None and search.strip():
        query = query.where(Holiday.name.ilike(f"%{search.strip()}%"))

    count_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = count_result.scalar_one()

    items_result = await db.execute(
        query.order_by(Holiday.holidayDate.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(items_result.scalars().all()), total


async def list_holidays_for_calendar(
    db: AsyncSession,
    organization_id: str,
    *,
    year: int | None = None,
    month: int | None = None,
) -> list[Holiday]:
    """Lightweight fetch used by the sidebar calendar — no pagination."""
    query = select(Holiday).where(
        Holiday.organizationId == organization_id,
        Holiday.deletedAt.is_(None),
        Holiday.isHoliday.is_(True),
    )
    if year is not None:
        query = query.where(func.extract("year", Holiday.holidayDate) == year)
    if month is not None:
        query = query.where(func.extract("month", Holiday.holidayDate) == month)
    result = await db.execute(query.order_by(Holiday.holidayDate.asc()))
    return list(result.scalars().all())


async def create_holiday(
    db: AsyncSession,
    organization_id: str,
    *,
    name: str,
    holiday_date: dt.date,
    is_recurring: bool,
    description: str | None,
) -> Holiday:
    now = _utcnow()
    holiday = Holiday(
        id=generate_uuid(),
        organizationId=organization_id,
        name=name.strip(),
        holidayDate=holiday_date,
        isRecurring=is_recurring,
        description=description,
        createdAt=now,
        updatedAt=now,
    )
    db.add(holiday)
    await db.commit()
    await db.refresh(holiday)
    return holiday


async def update_holiday(
    db: AsyncSession,
    organization_id: str,
    holiday_id: str,
    *,
    name: str,
    holiday_date: dt.date,
    is_recurring: bool,
    description: str | None,
) -> Holiday:
    holiday = await get_holiday_or_404(db, organization_id, holiday_id)
    holiday.name = name.strip()
    holiday.holidayDate = holiday_date
    holiday.isRecurring = is_recurring
    holiday.description = description
    holiday.updatedAt = _utcnow()
    await db.commit()
    await db.refresh(holiday)
    return holiday


async def delete_holiday(db: AsyncSession, organization_id: str, holiday_id: str) -> None:
    holiday = await get_holiday_or_404(db, organization_id, holiday_id)
    now = _utcnow()
    holiday.deletedAt = now
    holiday.updatedAt = now
    await db.commit()


def _apply_leave_request_filters(
    query,
    filters: LeaveRequestFilters,
    organization_scope: bool,
):
    if filters.status is not None:
        query = query.filter(LeaveRequest.status == filters.status)
    if organization_scope and filters.member_id is not None:
        query = query.filter(LeaveRequest.memberId == filters.member_id)
    if filters.leave_type_id is not None:
        query = query.filter(LeaveRequest.leaveTypeId == filters.leave_type_id)
    if filters.from_date is not None:
        query = query.filter(LeaveRequest.endDate >= filters.from_date)
    if filters.to_date is not None:
        query = query.filter(LeaveRequest.startDate <= filters.to_date)
    if filters.year is not None:
        query = query.filter(func.extract("year", LeaveRequest.startDate) == filters.year)
    return query


async def list_leave_requests(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    permission_scope: str,
    filters: LeaveRequestFilters,
) -> tuple[list[LeaveRequest], int]:
    query = (
        select(LeaveRequest)
        .options(
            joinedload(LeaveRequest.member).joinedload(Member.user),
            joinedload(LeaveRequest.approved_by).joinedload(Member.user),
            joinedload(LeaveRequest.leave_type),
        )
        .where(
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.deletedAt.is_(None),
        )
    )

    if permission_scope == "self":
        query = query.where(LeaveRequest.memberId == actor_member_id)
        organization_scope = False
    elif permission_scope == "department":
        from app.models.department_member import DepartmentMember
        department_subq = (
            select(DepartmentMember.memberId)
            .where(DepartmentMember.departmentId.in_(
                select(DepartmentMember.departmentId)
                .where(DepartmentMember.memberId == actor_member_id)
            ))
        )
        query = query.where(LeaveRequest.memberId.in_(department_subq))
        organization_scope = True
    else:
        organization_scope = True

    query = _apply_leave_request_filters(query, filters, organization_scope)
    total_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = total_result.scalar_one()
    items_result = await db.execute(
        query.order_by(LeaveRequest.createdAt.desc())
        .offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
    )
    items = items_result.unique().scalars().all()
    return items, total


async def get_leave_request_detail(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    permission_scope: str,
    leave_request_id: str,
) -> LeaveRequest:
    leave_request = await get_leave_request_or_404(db, organization_id, leave_request_id)
    if permission_scope == "self" and leave_request.memberId != actor_member_id:
        raise HTTPException(status_code=403, detail="You can only view your own leave requests")
    return leave_request


async def _ensure_no_overlapping_request(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    start_date: dt.date,
    end_date: dt.date,
) -> None:
    result = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.memberId == member_id,
            LeaveRequest.deletedAt.is_(None),
            LeaveRequest.status.in_([LeaveRequestStatus.PENDING.value, LeaveRequestStatus.APPROVED.value]),
            LeaveRequest.startDate <= end_date,
            LeaveRequest.endDate >= start_date,
        )
    )
    overlap = result.scalar_one_or_none()
    if overlap is not None:
        raise HTTPException(status_code=409, detail="An overlapping leave request already exists")


async def _get_or_create_leave_balance(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    leave_type: LeaveType,
    year: int,
) -> LeaveBalance:
    result = await db.execute(
        select(LeaveBalance).where(
            LeaveBalance.organizationId == organization_id,
            LeaveBalance.memberId == member_id,
            LeaveBalance.leaveTypeId == leave_type.id,
            LeaveBalance.year == year,
        )
    )
    balance = result.scalar_one_or_none()
    if balance is not None:
        return balance

    now = _utcnow()
    approved_used = await _get_approved_leave_days(
        db,
        organization_id,
        member_id,
        leave_type.id,
        year,
    )
    balance = LeaveBalance(
        id=generate_uuid(),
        organizationId=organization_id,
        memberId=member_id,
        leaveTypeId=leave_type.id,
        year=year,
        allocated=leave_type.quota,
        used=approved_used,
        remaining=leave_type.quota - approved_used,
        carriedForward=0,
        lapsed=0,
        createdAt=now,
        updatedAt=now,
    )
    db.add(balance)
    await db.flush()
    await db.refresh(balance)
    return balance


async def _count_working_days(
    db: AsyncSession,
    organization_id: str,
    start_date: dt.date,
    end_date: dt.date,
) -> int:
    """Count calendar days between start_date and end_date, excluding weekends and holidays."""
    total = 0
    current = start_date
    # Fetch holidays in range
    result = await db.execute(
        select(Holiday).where(
            Holiday.organizationId == organization_id,
            Holiday.deletedAt.is_(None),
            Holiday.isHoliday.is_(True),
            Holiday.holidayDate >= start_date,
            Holiday.holidayDate <= end_date,
        )
    )
    holiday_dates = {row.holidayDate for row in result.scalars().all()}

    while current <= end_date:
        if current.weekday() < 5 and current not in holiday_dates:
            total += 1
        current += dt.timedelta(days=1)
    return total


async def create_leave_request(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    create_scope: str,
    *,
    leave_type_id: str,
    member_id: str | None,
    start_date: dt.date,
    end_date: dt.date,
    days: float,
    reason: str | None,
) -> LeaveRequest:
    leave_type = await get_leave_type_or_404(db, organization_id, leave_type_id)

    target_member_id = actor_member_id

    await resolve_target_member(db, organization_id, target_member_id)
    await _ensure_no_overlapping_request(db, organization_id, target_member_id, start_date, end_date)

    working_days = await _count_working_days(db, organization_id, start_date, end_date)
    chargeable_days = min(days, float(working_days))

    # A request should only reserve eligibility; the actual balance is consumed on approval.
    if leave_type.isPaid:
        balance = await _get_or_create_leave_balance(
            db,
            organization_id,
            target_member_id,
            leave_type,
            start_date.year,
        )
        projected_remaining = (
            balance.allocated + balance.carriedForward - balance.used - balance.lapsed
        ) - chargeable_days
        if projected_remaining < 0:
            raise HTTPException(status_code=400, detail="Insufficient leave balance")

    now = _utcnow()
    leave_request = LeaveRequest(
        id=generate_uuid(),
        organizationId=organization_id,
        memberId=target_member_id,
        leaveTypeId=leave_type.id,
        startDate=start_date,
        endDate=end_date,
        days=chargeable_days,
        reason=reason,
        status=LeaveRequestStatus.PENDING.value,
        approvedById=None,
        approverComment=None,
        createdAt=now,
        updatedAt=now,
    )
    db.add(leave_request)
    await db.commit()
    return await get_leave_request_or_404(db, organization_id, leave_request.id)


async def approve_leave_request(
    db: AsyncSession,
    organization_id: str,
    approver_member_id: str,
    leave_request_id: str,
    approver_comment: str | None,
) -> LeaveRequest:
    leave_request = await get_leave_request_or_404(db, organization_id, leave_request_id)
    if leave_request.status != LeaveRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be approved")

    leave_type = await get_leave_type_or_404(db, organization_id, leave_request.leaveTypeId)
    now = _utcnow()
    balance = await _get_or_create_leave_balance(
        db,
        organization_id,
        leave_request.memberId,
        leave_type,
        leave_request.startDate.year,
    )
    current_used = await _get_approved_leave_days(
        db,
        organization_id,
        leave_request.memberId,
        leave_type.id,
        leave_request.startDate.year,
    )
    new_used = current_used + leave_request.days
    new_remaining = balance.allocated + balance.carriedForward - new_used - balance.lapsed
    if new_remaining < 0:
        raise HTTPException(status_code=400, detail="Approving this request would make the leave balance negative")

    balance.used = new_used
    balance.remaining = new_remaining
    balance.updatedAt = now

    leave_request.status = LeaveRequestStatus.APPROVED.value
    leave_request.approvedById = approver_member_id
    leave_request.approverComment = approver_comment
    leave_request.cancelledAt = None
    leave_request.updatedAt = now
    await db.commit()
    return await get_leave_request_or_404(db, organization_id, leave_request_id)


async def reject_leave_request(
    db: AsyncSession,
    organization_id: str,
    approver_member_id: str,
    leave_request_id: str,
    approver_comment: str | None,
) -> LeaveRequest:
    leave_request = await get_leave_request_or_404(db, organization_id, leave_request_id)
    if leave_request.status != LeaveRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be rejected")

    now = _utcnow()
    leave_request.status = LeaveRequestStatus.REJECTED.value
    leave_request.approvedById = approver_member_id
    leave_request.approverComment = approver_comment
    leave_request.updatedAt = now
    await db.commit()
    return await get_leave_request_or_404(db, organization_id, leave_request_id)


async def cancel_leave_request(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    *,
    leave_request_id: str,
    can_cancel_any: bool,
) -> LeaveRequest:
    leave_request = await get_leave_request_or_404(db, organization_id, leave_request_id)
    if leave_request.status != LeaveRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be cancelled")
    if not can_cancel_any and leave_request.memberId != actor_member_id:
        raise HTTPException(status_code=403, detail="You can only cancel your own pending leave requests")

    now = _utcnow()
    leave_request.status = LeaveRequestStatus.CANCELLED.value
    leave_request.cancelledAt = now
    leave_request.updatedAt = now
    await db.commit()
    return await get_leave_request_or_404(db, organization_id, leave_request_id)


async def list_leave_balances(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    permission_scope: str,
    filters: LeaveBalanceFilters,
) -> tuple[list[LeaveBalanceRow], int]:
    """
    Return a balance row for every (member, leave_type) combination in the org.
    Leave types that have never been used still appear with zero values.
    """
    year = filters.year or dt.date.today().year
    _now = dt.datetime.now(dt.UTC)

    # ── 1. Resolve which members to include ──────────────────────────────────
    member_query = (
        select(Member)
        .options(joinedload(Member.user))
        .where(Member.organizationId == organization_id)
    )
    if permission_scope == "self":
        member_query = member_query.where(Member.id == actor_member_id)
    elif filters.member_id is not None:
        member_query = member_query.where(Member.id == filters.member_id)
    else:
        member_query = member_query.where(Member.status == "ACTIVE")  # status: ACTIVE only

    members_result = await db.execute(member_query)
    members = members_result.unique().scalars().all()

    # ── 2. Resolve which leave types to include ───────────────────────────────
    lt_query = (
        select(LeaveType)
        .where(
            LeaveType.organizationId == organization_id,
            LeaveType.deletedAt.is_(None),
        )
        .order_by(LeaveType.name.asc())
    )
    if filters.leave_type_id is not None:
        lt_query = lt_query.where(LeaveType.id == filters.leave_type_id)

    lt_result = await db.execute(lt_query)
    leave_types = lt_result.scalars().all()

    # ── 3. Fetch existing balance records for this year ───────────────────────
    member_ids = [m.id for m in members]
    lt_ids = [lt.id for lt in leave_types]

    existing_query = select(LeaveBalance).where(
        LeaveBalance.organizationId == organization_id,
        LeaveBalance.year == year,
        LeaveBalance.memberId.in_(member_ids),
        LeaveBalance.leaveTypeId.in_(lt_ids),
    )
    existing_result = await db.execute(existing_query)
    existing_balances: dict[tuple[str, str], LeaveBalance] = {
        (b.memberId, b.leaveTypeId): b for b in existing_result.scalars().all()
    }

    approved_usage_result = await db.execute(
        select(
            LeaveRequest.memberId,
            LeaveRequest.leaveTypeId,
            func.coalesce(func.sum(LeaveRequest.days), 0.0),
        )
        .where(
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.status == LeaveRequestStatus.APPROVED.value,
            LeaveRequest.deletedAt.is_(None),
            LeaveRequest.startDate >= dt.date(year, 1, 1),
            LeaveRequest.startDate < dt.date(year + 1, 1, 1),
            LeaveRequest.memberId.in_(member_ids),
            LeaveRequest.leaveTypeId.in_(lt_ids),
        )
        .group_by(LeaveRequest.memberId, LeaveRequest.leaveTypeId)
    )
    approved_usage: dict[tuple[str, str], float] = {
        (member_id, leave_type_id): float(total or 0.0)
        for member_id, leave_type_id, total in approved_usage_result.all()
    }

    # ── 4. Build synthetic rows for every (member × leave_type) ──────────────
    rows: list[LeaveBalanceRow] = []
    for member in members:
        for lt in leave_types:
            balance = existing_balances.get((member.id, lt.id))
            if balance is not None:
                actual_used = approved_usage.get((member.id, lt.id), 0.0)
                actual_remaining = balance.allocated + balance.carriedForward - actual_used - balance.lapsed
                rows.append(
                    LeaveBalanceRow(
                        id=balance.id,
                        organizationId=balance.organizationId,
                        memberId=balance.memberId,
                        leaveTypeId=balance.leaveTypeId,
                        year=balance.year,
                        allocated=balance.allocated,
                        used=actual_used,
                        remaining=actual_remaining,
                        carriedForward=balance.carriedForward,
                        lapsed=balance.lapsed,
                        createdAt=balance.createdAt,
                        updatedAt=balance.updatedAt,
                        member=member,
                        leave_type=lt,
                    )
                )
            else:
                actual_used = approved_usage.get((member.id, lt.id), 0.0)
                rows.append(
                    LeaveBalanceRow(
                        id=f"virtual-{member.id}-{lt.id}",
                        organizationId=organization_id,
                        memberId=member.id,
                        leaveTypeId=lt.id,
                        year=year,
                        allocated=lt.quota,
                        used=actual_used,
                        remaining=lt.quota - actual_used,
                        carriedForward=0.0,
                        lapsed=0.0,
                        createdAt=_now,
                        updatedAt=_now,
                        member=member,
                        leave_type=lt,
                    )
                )

    # ── 5. Client-side search filter ──────────────────────────────────────────
    if filters.search:
        q = filters.search.lower()
        rows = [
            r for r in rows
            if q in (r.member.user.name or '').lower()
            or q in (r.member.user.email or '').lower()
            or q in r.leave_type.name.lower()
        ]

    # ── 6. Sort: by member name then leave type name ─────────────────────────
    rows.sort(key=lambda r: (
        (r.member.user.name or r.member.user.email or r.memberId).lower()
        if r.member.user else r.memberId,
        r.leave_type.name.lower(),
    ))

    total = len(rows)

    # ── 7. Paginate ──────────────────────────────────────────────────────────
    offset = (filters.page - 1) * filters.page_size
    paged = rows[offset : offset + filters.page_size]

    return paged, total


async def upsert_leave_balance(
    db: AsyncSession,
    organization_id: str,
    *,
    member_id: str,
    leave_type_id: str,
    year: int,
    allocated: float,
    carried_forward: float,
    lapsed: float,
) -> LeaveBalance:
    await resolve_target_member(db, organization_id, member_id)
    leave_type = await get_leave_type_or_404(db, organization_id, leave_type_id)

    result = await db.execute(
        select(LeaveBalance).where(
            LeaveBalance.organizationId == organization_id,
            LeaveBalance.memberId == member_id,
            LeaveBalance.leaveTypeId == leave_type.id,
            LeaveBalance.year == year,
        )
    )
    balance = result.scalar_one_or_none()
    now = _utcnow()
    if balance is None:
        approved_used = await _get_approved_leave_days(
            db,
            organization_id,
            member_id,
            leave_type.id,
            year,
        )
        balance = LeaveBalance(
            id=generate_uuid(),
            organizationId=organization_id,
            memberId=member_id,
            leaveTypeId=leave_type.id,
            year=year,
            used=approved_used,
            createdAt=now,
            updatedAt=now,
        )
        db.add(balance)

    actual_used = await _get_approved_leave_days(
        db,
        organization_id,
        member_id,
        leave_type.id,
        year,
    )
    remaining = allocated + carried_forward - actual_used - lapsed
    if remaining < 0:
        raise HTTPException(
            status_code=400,
            detail="Assigned balance cannot be lower than already used leave days",
        )

    balance.allocated = allocated
    balance.used = actual_used
    balance.carriedForward = carried_forward
    balance.lapsed = lapsed
    balance.remaining = remaining
    balance.updatedAt = now

    await db.commit()

    refreshed = await db.execute(
        select(LeaveBalance)
        .options(
            joinedload(LeaveBalance.member).joinedload(Member.user),
            joinedload(LeaveBalance.leave_type),
        )
        .where(LeaveBalance.id == balance.id)
    )
    return refreshed.unique().scalar_one()


def _resolve_calendar_range(filters: LeaveCalendarFilters) -> tuple[dt.date, dt.date]:
    if filters.from_date is not None and filters.to_date is not None:
        if filters.to_date < filters.from_date:
            raise HTTPException(status_code=400, detail="toDate must be on or after fromDate")
        return filters.from_date, filters.to_date

    today = dt.date.today()
    year = filters.year or today.year
    month = filters.month or today.month
    start = dt.date(year, month, 1)
    if month == 12:
        end = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
    else:
        end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    return start, end


async def get_leave_calendar(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    permission_scope: str,
    filters: LeaveCalendarFilters,
) -> tuple[list[Holiday], list[LeaveRequest]]:
    range_start, range_end = _resolve_calendar_range(filters)

    holidays_result = await db.execute(
        select(Holiday).where(
            Holiday.organizationId == organization_id,
            Holiday.deletedAt.is_(None),
            Holiday.holidayDate >= range_start,
            Holiday.holidayDate <= range_end,
        )
        .order_by(Holiday.holidayDate.asc())
    )
    holidays = holidays_result.scalars().all()
    query = (
        select(LeaveRequest)
        .options(
            joinedload(LeaveRequest.member).joinedload(Member.user),
            joinedload(LeaveRequest.approved_by).joinedload(Member.user),
            joinedload(LeaveRequest.leave_type),
        )
        .where(
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.deletedAt.is_(None),
            LeaveRequest.startDate <= range_end,
            LeaveRequest.endDate >= range_start,
        )
    )
    if permission_scope == "self":
        query = query.where(LeaveRequest.memberId == actor_member_id)

    leave_requests_result = await db.execute(
        query.order_by(LeaveRequest.startDate.asc(), LeaveRequest.createdAt.desc())
    )
    leave_requests = leave_requests_result.unique().scalars().all()
    return holidays, leave_requests


async def get_leave_summary(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    permission_scope: str,
) -> list[tuple[str, str | None, str | None, float, list[LeaveRequest]]]:
    member_query = (
        select(Member)
        .join(Member.user)
        .options(contains_eager(Member.user))
        .where(Member.organizationId == organization_id)
    )
    if permission_scope == "self":
        member_query = member_query.where(Member.id == actor_member_id)
    else:
        member_query = member_query.where(Member.status == "ACTIVE")  # status: ACTIVE only

    members_result = await db.execute(member_query)
    all_members = members_result.unique().scalars().all()

    requests_query = (
        select(LeaveRequest)
        .options(
            joinedload(LeaveRequest.member).joinedload(Member.user),
            joinedload(LeaveRequest.leave_type),
        )
        .where(
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.deletedAt.is_(None),
            LeaveRequest.status == LeaveRequestStatus.APPROVED.value,
        )
    )

    requests_result = await db.execute(
        requests_query.order_by(LeaveRequest.memberId, LeaveRequest.startDate.asc())
    )
    all_requests = requests_result.unique().scalars().all()

    leave_map: dict[str, list[LeaveRequest]] = {}
    for req in all_requests:
        leave_map.setdefault(req.memberId, []).append(req)

    rows: list[tuple[str, str | None, str | None, float, list[LeaveRequest]]] = []
    for member in all_members:
        member_id = member.id
        name = member.user.name if member.user else None
        email = member.user.email if member.user else None
        items = leave_map.get(member_id, [])
        total_days = sum(req.days for req in items)
        rows.append((member_id, name, email, total_days, items))

    rows.sort(key=lambda x: (x[1] or x[2] or "").lower())
    return rows
