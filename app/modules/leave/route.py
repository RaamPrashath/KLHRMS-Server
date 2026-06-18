"""Leave module routes."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.leave.controller import (
    handle_approve_leave_request,
    handle_cancel_leave_request,
    handle_create_holiday,
    handle_create_leave_request,
    handle_create_leave_type,
    handle_delete_holiday,
    handle_get_leave_calendar,
    handle_get_leave_request,
    handle_get_leave_summary,
    handle_list_holidays,
    handle_list_leave_balances,
    handle_list_leave_requests,
    handle_list_leave_types,
    handle_reject_leave_request,
    handle_update_holiday,
    handle_update_leave_type,
    handle_upsert_leave_balance,
)
from app.modules.leave.permissions import LeaveAccessContext, require_leave_permission
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
    LeaveSummaryListResponse,
    LeaveTypeCreateRequest,
    LeaveTypeResponse,
    LeaveTypeUpdateRequest,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context

router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.get("/types", response_model=list[LeaveTypeResponse], status_code=status.HTTP_200_OK)
async def list_leave_types(
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: AsyncSession = Depends(get_db),
) -> list[LeaveTypeResponse]:
    return await handle_list_leave_types(ctx, db)


@router.post("/types", response_model=LeaveTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_type(
    body: LeaveTypeCreateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> LeaveTypeResponse:
    return await handle_create_leave_type(access, db, body)


@router.patch("/types/{leave_type_id}", response_model=LeaveTypeResponse, status_code=status.HTTP_200_OK)
async def update_leave_type(
    leave_type_id: str,
    body: LeaveTypeUpdateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> LeaveTypeResponse:
    return await handle_update_leave_type(access, db, leave_type_id, body)


@router.get("/holidays", response_model=HolidayListResponse, status_code=status.HTTP_200_OK)
async def list_holidays(
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: AsyncSession = Depends(get_db),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    search: str | None = Query(default=None, max_length=255),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500, alias="pageSize"),
) -> HolidayListResponse:
    import time as _time
    _t0 = _time.perf_counter()
    filters = HolidayListFilters(
        year=year,
        month=month,
        search=search,
        page=page,
        page_size=page_size,
    )
    result = await handle_list_holidays(ctx, db, filters=filters)
    _t1 = _time.perf_counter()
    import logging
    logging.warning(
        "[timing] route:list_holidays | year=%s month=%s | duration=%.1fms | items=%d",
        year, month, (_t1 - _t0) * 1000, len(result.items),
    )
    return result


@router.post("/holidays", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_holiday(
    body: HolidayCreateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> HolidayResponse:
    return await handle_create_holiday(access, db, body)


@router.patch("/holidays/{holiday_id}", response_model=HolidayResponse, status_code=status.HTTP_200_OK)
async def update_holiday(
    holiday_id: str,
    body: HolidayUpdateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> HolidayResponse:
    return await handle_update_holiday(access, db, holiday_id, body)


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(
    holiday_id: str,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> Response:
    await handle_delete_holiday(access, db, holiday_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/requests", response_model=LeaveRequestListResponse, status_code=status.HTTP_200_OK)
async def list_leave_requests(
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("view"))],
    db: AsyncSession = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    member_id: str | None = Query(default=None, alias="memberId"),
    leave_type_id: str | None = Query(default=None, alias="leaveTypeId"),
    from_date: dt.date | None = Query(default=None, alias="fromDate"),
    to_date: dt.date | None = Query(default=None, alias="toDate"),
    year: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
) -> LeaveRequestListResponse:
    import time as _time
    _t0 = _time.perf_counter()
    filters = LeaveRequestFilters(
        status=status_filter,
        member_id=member_id,
        leave_type_id=leave_type_id,
        from_date=from_date,
        to_date=to_date,
        year=year,
        page=page,
        page_size=page_size,
    )
    result = await handle_list_leave_requests(access, db, filters)
    _t1 = _time.perf_counter()
    import logging
    logging.warning(
        "[timing] route:list_leave_requests | status=%s from=%s to=%s | duration=%.1fms | items=%d",
        status_filter, from_date, to_date, (_t1 - _t0) * 1000, len(result.items),
    )
    return result


@router.get("/requests/{leave_request_id}", response_model=LeaveRequestResponse, status_code=status.HTTP_200_OK)
async def get_leave_request(
    leave_request_id: str,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("view"))],
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    return await handle_get_leave_request(access, db, leave_request_id)


@router.post("/requests", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    body: LeaveRequestCreateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("create"))],
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    return await handle_create_leave_request(access, db, body)


@router.post("/requests/{leave_request_id}/approve", response_model=LeaveRequestResponse, status_code=status.HTTP_200_OK)
async def approve_leave_request(
    leave_request_id: str,
    body: LeaveRequestDecisionRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    return await handle_approve_leave_request(access, db, leave_request_id, body)


@router.post("/requests/{leave_request_id}/reject", response_model=LeaveRequestResponse, status_code=status.HTTP_200_OK)
async def reject_leave_request(
    leave_request_id: str,
    body: LeaveRequestDecisionRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    return await handle_reject_leave_request(access, db, leave_request_id, body)


@router.post("/requests/{leave_request_id}/cancel", response_model=LeaveRequestResponse, status_code=status.HTTP_200_OK)
async def cancel_leave_request(
    leave_request_id: str,
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    return await handle_cancel_leave_request(ctx, db, leave_request_id)


@router.get("/balances", response_model=LeaveBalanceListResponse, status_code=status.HTTP_200_OK)
async def list_leave_balances(
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("view"))],
    db: AsyncSession = Depends(get_db),
    year: int | None = Query(default=None),
    member_id: str | None = Query(default=None, alias="memberId"),
    leave_type_id: str | None = Query(default=None, alias="leaveTypeId"),
    search: str | None = Query(default=None, max_length=255),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500, alias="pageSize"),
) -> LeaveBalanceListResponse:
    filters = LeaveBalanceFilters(
        year=year,
        member_id=member_id,
        leave_type_id=leave_type_id,
        search=search,
        page=page,
        page_size=page_size,
    )
    return await handle_list_leave_balances(access, db, filters)


@router.put("/balances", response_model=LeaveBalanceResponse, status_code=status.HTTP_200_OK)
async def upsert_leave_balance(
    body: LeaveBalanceUpsertRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> LeaveBalanceResponse:
    return await handle_upsert_leave_balance(access, db, body)


@router.get("/summary", response_model=LeaveSummaryListResponse, status_code=status.HTTP_200_OK)
async def get_leave_summary(
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: AsyncSession = Depends(get_db),
) -> LeaveSummaryListResponse:
    return await handle_get_leave_summary(access, db)


@router.get("/calendar", response_model=LeaveCalendarResponse, status_code=status.HTTP_200_OK)
async def get_leave_calendar(
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("view"))],
    db: AsyncSession = Depends(get_db),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    from_date: dt.date | None = Query(default=None, alias="fromDate"),
    to_date: dt.date | None = Query(default=None, alias="toDate"),
) -> LeaveCalendarResponse:
    filters = LeaveCalendarFilters(
        year=year,
        month=month,
        from_date=from_date,
        to_date=to_date,
    )
    return await handle_get_leave_calendar(access, db, filters)
