"""Core business logic for the leave module."""

from __future__ import annotations

import datetime as dt

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.base import generate_uuid
from app.models.leave import Holiday, LeaveBalance, LeaveRequest, LeaveType
from app.models.member import Member
from app.modules.leave.schema import LeaveBalanceFilters, LeaveCalendarFilters, LeaveRequestFilters
from app.shared.utils.enums import LeaveRequestStatus


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


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
    await _ensure_leave_type_name_available(db, organization_id, name)

    leave_type = LeaveType(
        id=generate_uuid(),
        organizationId=organization_id,
        name=name.strip(),
        quota=quota,
        carryForward=carry_forward,
        isPaid=is_paid,
        color=color,
    )
    db.add(leave_type)

    try:
        await db.commit()
        await db.refresh(leave_type)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Failed to create leave type") from exc
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

    leave_type.name = name.strip()
    leave_type.quota = quota
    leave_type.carryForward = carry_forward
    leave_type.isPaid = is_paid
    leave_type.color = color

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
) -> list[Holiday]:
    query = select(Holiday).where(
        Holiday.organizationId == organization_id,
        Holiday.deletedAt.is_(None),
    )
    if year is not None:
        query = query.where(func.extract("year", Holiday.holidayDate) == year)
    if month is not None:
        query = query.where(func.extract("month", Holiday.holidayDate) == month)
    result = await db.execute(query.order_by(Holiday.holidayDate.asc()))
    return result.scalars().all()


async def create_holiday(
    db: AsyncSession,
    organization_id: str,
    *,
    name: str,
    holiday_date: dt.date,
    is_recurring: bool,
    description: str | None,
) -> Holiday:
    holiday = Holiday(
        id=generate_uuid(),
        organizationId=organization_id,
        name=name.strip(),
        holidayDate=holiday_date,
        isRecurring=is_recurring,
        description=description,
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
    await db.commit()
    await db.refresh(holiday)
    return holiday


async def delete_holiday(db: AsyncSession, organization_id: str, holiday_id: str) -> None:
    holiday = await get_holiday_or_404(db, organization_id, holiday_id)
    holiday.deletedAt = _utcnow()
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
            LeaveRequest.status.in_([LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED]),
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

    balance = LeaveBalance(
        id=generate_uuid(),
        organizationId=organization_id,
        memberId=member_id,
        leaveTypeId=leave_type.id,
        year=year,
        allocated=leave_type.quota,
        used=0,
        remaining=leave_type.quota,
        carriedForward=0,
        lapsed=0,
    )
    db.add(balance)
    await db.flush()
    await db.refresh(balance)
    return balance


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

    target_member_id = actor_member_id if create_scope == "self" else (member_id or actor_member_id)
    if create_scope == "self" and target_member_id != actor_member_id:
        raise HTTPException(status_code=403, detail="You can only create leave requests for yourself")

    await resolve_target_member(db, organization_id, target_member_id)
    await _ensure_no_overlapping_request(db, organization_id, target_member_id, start_date, end_date)

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
        ) - days
        if projected_remaining < 0:
            raise HTTPException(status_code=400, detail="Insufficient leave balance")

    leave_request = LeaveRequest(
        id=generate_uuid(),
        organizationId=organization_id,
        memberId=target_member_id,
        leaveTypeId=leave_type.id,
        startDate=start_date,
        endDate=end_date,
        days=days,
        reason=reason,
        status=LeaveRequestStatus.PENDING,
        approvedById=None,
        approverComment=None,
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
    if leave_request.status != LeaveRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be approved")

    leave_type = await get_leave_type_or_404(db, organization_id, leave_request.leaveTypeId)
    if leave_type.isPaid:
        balance = await _get_or_create_leave_balance(
            db,
            organization_id,
            leave_request.memberId,
            leave_type,
            leave_request.startDate.year,
        )
        new_used = balance.used + leave_request.days
        new_remaining = balance.allocated + balance.carriedForward - new_used - balance.lapsed
        if new_remaining < 0:
            raise HTTPException(status_code=400, detail="Approving this request would make the leave balance negative")
        balance.used = new_used
        balance.remaining = new_remaining

    leave_request.status = LeaveRequestStatus.APPROVED
    leave_request.approvedById = approver_member_id
    leave_request.approverComment = approver_comment
    leave_request.cancelledAt = None
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
    if leave_request.status != LeaveRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be rejected")

    leave_request.status = LeaveRequestStatus.REJECTED
    leave_request.approvedById = approver_member_id
    leave_request.approverComment = approver_comment
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
    if leave_request.status != LeaveRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending leave requests can be cancelled")
    if not can_cancel_any and leave_request.memberId != actor_member_id:
        raise HTTPException(status_code=403, detail="You can only cancel your own pending leave requests")

    leave_request.status = LeaveRequestStatus.CANCELLED
    leave_request.cancelledAt = _utcnow()
    await db.commit()
    return await get_leave_request_or_404(db, organization_id, leave_request_id)


async def list_leave_balances(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    permission_scope: str,
    filters: LeaveBalanceFilters,
) -> tuple[list[LeaveBalance], int]:
    query = (
        select(LeaveBalance)
        .options(
            joinedload(LeaveBalance.member).joinedload(Member.user),
            joinedload(LeaveBalance.leave_type),
        )
        .where(LeaveBalance.organizationId == organization_id)
    )
    if permission_scope == "self":
        query = query.where(LeaveBalance.memberId == actor_member_id)
    elif filters.member_id is not None:
        query = query.where(LeaveBalance.memberId == filters.member_id)

    if filters.year is not None:
        query = query.where(LeaveBalance.year == filters.year)
    if filters.leave_type_id is not None:
        query = query.where(LeaveBalance.leaveTypeId == filters.leave_type_id)

    total_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = total_result.scalar_one()
    items_result = await db.execute(
        query.join(LeaveType, LeaveType.id == LeaveBalance.leaveTypeId)
        .order_by(LeaveBalance.year.desc(), LeaveType.name.asc())
    )
    items = items_result.unique().scalars().all()
    return items, total


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
