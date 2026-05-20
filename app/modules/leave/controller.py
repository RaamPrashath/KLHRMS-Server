"""Thin orchestration layer for leave module responses."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave import Holiday, LeaveBalance, LeaveRequest, LeaveType
from app.models.member import Member
from app.modules.leave import service
from app.modules.leave.permissions import LeaveAccessContext, get_permission_scope
from app.modules.leave.schema import (
    HolidayCreateRequest,
    HolidayListFilters,
    HolidayListResponse,
    HolidayResponse,
    HolidayUpdateRequest,
    LeaveBalanceFilters,
    LeaveBalanceListResponse,
    LeaveBalanceResponse,
    LeaveBalanceUpsertRequest,
    LeaveCalendarFilters,
    LeaveCalendarResponse,
    LeaveRequestCreateRequest,
    LeaveRequestDecisionRequest,
    LeaveRequestFilters,
    LeaveRequestListResponse,
    LeaveRequestResponse,
    LeaveTypeCreateRequest,
    LeaveTypeResponse,
    LeaveTypeUpdateRequest,
    MemberSummaryResponse,
)
from app.shared.deps.organization_member import MemberContext


def _member_summary(member: Member | None) -> MemberSummaryResponse | None:
    if member is None:
        return None
    return MemberSummaryResponse(
        memberId=member.id,
        userId=member.userId,
        name=member.user.name if member.user is not None else None,
        email=member.user.email if member.user is not None else None,
    )


def _leave_type_response(leave_type: LeaveType) -> LeaveTypeResponse:
    return LeaveTypeResponse.model_validate(leave_type)


def _leave_request_response(leave_request: LeaveRequest) -> LeaveRequestResponse:
    return LeaveRequestResponse(
        id=leave_request.id,
        organizationId=leave_request.organizationId,
        memberId=leave_request.memberId,
        leaveTypeId=leave_request.leaveTypeId,
        startDate=leave_request.startDate,
        endDate=leave_request.endDate,
        days=leave_request.days,
        reason=leave_request.reason,
        status=leave_request.status,
        approvedById=leave_request.approvedById,
        approverComment=leave_request.approverComment,
        cancelledAt=leave_request.cancelledAt,
        createdAt=leave_request.createdAt,
        updatedAt=leave_request.updatedAt,
        member=_member_summary(leave_request.member),
        approver=_member_summary(leave_request.approved_by),
        leaveType=_leave_type_response(leave_request.leave_type),
    )


def _holiday_response(holiday: Holiday) -> HolidayResponse:
    return HolidayResponse.model_validate(holiday)


def _leave_balance_response(balance: LeaveBalance | service.LeaveBalanceRow) -> LeaveBalanceResponse:
    return LeaveBalanceResponse(
        id=balance.id,
        organizationId=balance.organizationId,
        memberId=balance.memberId,
        leaveTypeId=balance.leaveTypeId,
        year=balance.year,
        allocated=balance.allocated,
        used=balance.used,
        remaining=balance.remaining,
        carriedForward=balance.carriedForward,
        lapsed=balance.lapsed,
        createdAt=balance.createdAt,
        updatedAt=balance.updatedAt,
        member=_member_summary(balance.member),
        leaveType=_leave_type_response(balance.leave_type),
    )


async def handle_list_leave_types(ctx: MemberContext, db: AsyncSession) -> list[LeaveTypeResponse]:
    return [_leave_type_response(item) for item in await service.list_leave_types(db, ctx.organization.id)]


async def handle_create_leave_type(
    access: LeaveAccessContext,
    db: AsyncSession,
    body: LeaveTypeCreateRequest,
) -> LeaveTypeResponse:
    leave_type = await service.create_leave_type(
        db,
        access.organization.id,
        name=body.name,
        quota=body.quota,
        carry_forward=body.carry_forward,
        is_paid=body.is_paid,
        color=body.color,
    )
    return _leave_type_response(leave_type)


async def handle_update_leave_type(
    access: LeaveAccessContext,
    db: AsyncSession,
    leave_type_id: str,
    body: LeaveTypeUpdateRequest,
) -> LeaveTypeResponse:
    leave_type = await service.update_leave_type(
        db,
        access.organization.id,
        leave_type_id,
        name=body.name,
        quota=body.quota,
        carry_forward=body.carry_forward,
        is_paid=body.is_paid,
        color=body.color,
    )
    return _leave_type_response(leave_type)


async def handle_list_holidays(
    ctx: MemberContext,
    db: AsyncSession,
    *,
    filters: HolidayListFilters,
) -> HolidayListResponse:
    items, total = await service.list_holidays(
        db,
        ctx.organization.id,
        year=filters.year,
        month=filters.month,
        search=filters.search,
        page=filters.page,
        page_size=filters.page_size,
    )
    return HolidayListResponse(
        items=[_holiday_response(item) for item in items],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


async def handle_create_holiday(
    access: LeaveAccessContext,
    db: AsyncSession,
    body: HolidayCreateRequest,
) -> HolidayResponse:
    holiday = await service.create_holiday(
        db,
        access.organization.id,
        name=body.name,
        holiday_date=body.holiday_date,
        is_recurring=body.is_recurring,
        description=body.description,
    )
    return _holiday_response(holiday)


async def handle_update_holiday(
    access: LeaveAccessContext,
    db: AsyncSession,
    holiday_id: str,
    body: HolidayUpdateRequest,
) -> HolidayResponse:
    holiday = await service.update_holiday(
        db,
        access.organization.id,
        holiday_id,
        name=body.name,
        holiday_date=body.holiday_date,
        is_recurring=body.is_recurring,
        description=body.description,
    )
    return _holiday_response(holiday)


async def handle_delete_holiday(
    access: LeaveAccessContext,
    db: AsyncSession,
    holiday_id: str,
) -> None:
    await service.delete_holiday(db, access.organization.id, holiday_id)


async def handle_list_leave_requests(
    access: LeaveAccessContext,
    db: AsyncSession,
    filters: LeaveRequestFilters,
) -> LeaveRequestListResponse:
    items, total = await service.list_leave_requests(
        db,
        access.organization.id,
        access.member.id,
        access.permission_scope,
        filters,
    )
    return LeaveRequestListResponse(
        items=[_leave_request_response(item) for item in items],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


async def handle_get_leave_request(
    access: LeaveAccessContext,
    db: AsyncSession,
    leave_request_id: str,
) -> LeaveRequestResponse:
    item = await service.get_leave_request_detail(
        db,
        access.organization.id,
        access.member.id,
        access.permission_scope,
        leave_request_id,
    )
    return _leave_request_response(item)


async def handle_create_leave_request(
    access: LeaveAccessContext,
    db: AsyncSession,
    body: LeaveRequestCreateRequest,
) -> LeaveRequestResponse:
    item = await service.create_leave_request(
        db,
        access.organization.id,
        access.member.id,
        access.permission_scope,
        leave_type_id=body.leave_type_id,
        member_id=body.member_id,
        start_date=body.start_date,
        end_date=body.end_date,
        days=body.days,
        reason=body.reason,
    )
    return _leave_request_response(item)


async def handle_approve_leave_request(
    access: LeaveAccessContext,
    db: AsyncSession,
    leave_request_id: str,
    body: LeaveRequestDecisionRequest,
) -> LeaveRequestResponse:
    item = await service.approve_leave_request(
        db,
        access.organization.id,
        access.member.id,
        leave_request_id,
        body.approver_comment,
    )
    return _leave_request_response(item)


async def handle_reject_leave_request(
    access: LeaveAccessContext,
    db: AsyncSession,
    leave_request_id: str,
    body: LeaveRequestDecisionRequest,
) -> LeaveRequestResponse:
    item = await service.reject_leave_request(
        db,
        access.organization.id,
        access.member.id,
        leave_request_id,
        body.approver_comment,
    )
    return _leave_request_response(item)


async def handle_cancel_leave_request(
    ctx: MemberContext,
    db: AsyncSession,
    leave_request_id: str,
) -> LeaveRequestResponse:
    permissions = ctx.role.permissions if ctx.role is not None else {}
    create_scope = get_permission_scope(permissions, "leaves", "create")
    approve_scope = get_permission_scope(permissions, "leaves", "approve")

    if create_scope is None and approve_scope is None:
        raise HTTPException(status_code=403, detail="No leaves.create or leaves.approve permission")

    can_cancel_any = create_scope == "organization" or approve_scope == "organization"
    item = await service.cancel_leave_request(
        db,
        ctx.organization.id,
        ctx.member.id,
        leave_request_id=leave_request_id,
        can_cancel_any=can_cancel_any,
    )
    return _leave_request_response(item)


async def handle_list_leave_balances(
    access: LeaveAccessContext,
    db: AsyncSession,
    filters: LeaveBalanceFilters,
) -> LeaveBalanceListResponse:
    items, total = await service.list_leave_balances(
        db,
        access.organization.id,
        access.member.id,
        access.permission_scope,
        filters,
    )
    return LeaveBalanceListResponse(
        items=[_leave_balance_response(item) for item in items],
        total=total,
    )


async def handle_upsert_leave_balance(
    access: LeaveAccessContext,
    db: AsyncSession,
    body: LeaveBalanceUpsertRequest,
) -> LeaveBalanceResponse:
    item = await service.upsert_leave_balance(
        db,
        access.organization.id,
        member_id=body.member_id,
        leave_type_id=body.leave_type_id,
        year=body.year,
        allocated=body.allocated,
        carried_forward=body.carried_forward,
        lapsed=body.lapsed,
    )
    return _leave_balance_response(item)


async def handle_get_leave_calendar(
    access: LeaveAccessContext,
    db: AsyncSession,
    filters: LeaveCalendarFilters,
) -> LeaveCalendarResponse:
    holidays, leave_requests = await service.get_leave_calendar(
        db,
        access.organization.id,
        access.member.id,
        access.permission_scope,
        filters,
    )
    return LeaveCalendarResponse(
        holidays=[_holiday_response(item) for item in holidays],
        leaveRequests=[_leave_request_response(item) for item in leave_requests],
    )
