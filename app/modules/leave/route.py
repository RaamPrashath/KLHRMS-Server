"""Leave module routes."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.modules.leave.controller import (
    handle_approve_leave_request,
    handle_cancel_leave_request,
    handle_create_holiday,
    handle_create_leave_request,
    handle_create_leave_type,
    handle_delete_holiday,
    handle_get_leave_calendar,
    handle_get_leave_request,
    handle_list_holidays,
    handle_list_leave_balances,
    handle_list_leave_requests,
    handle_list_leave_types,
    handle_reject_leave_request,
    handle_update_holiday,
    handle_update_leave_type,
)
from app.modules.leave.permissions import LeaveAccessContext, require_leave_permission
from app.modules.leave.schema import (
    HolidayCreateRequest,
    HolidayResponse,
    HolidayUpdateRequest,
    LeaveBalanceFilters,
    LeaveBalanceListResponse,
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
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context

router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.get("/types", response_model=list[LeaveTypeResponse], status_code=status.HTTP_200_OK)
def list_leave_types(
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: Session = Depends(get_db),
) -> list[LeaveTypeResponse]:
    return handle_list_leave_types(ctx, db)


@router.post("/types", response_model=LeaveTypeResponse, status_code=status.HTTP_201_CREATED)
def create_leave_type(
    body: LeaveTypeCreateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: Session = Depends(get_db),
) -> LeaveTypeResponse:
    return handle_create_leave_type(access, db, body)


@router.patch("/types/{leave_type_id}", response_model=LeaveTypeResponse, status_code=status.HTTP_200_OK)
def update_leave_type(
    leave_type_id: str,
    body: LeaveTypeUpdateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: Session = Depends(get_db),
) -> LeaveTypeResponse:
    return handle_update_leave_type(access, db, leave_type_id, body)


@router.get("/holidays", response_model=list[HolidayResponse], status_code=status.HTTP_200_OK)
def list_holidays(
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: Session = Depends(get_db),
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
) -> list[HolidayResponse]:
    return handle_list_holidays(ctx, db, year=year, month=month)


@router.post("/holidays", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
def create_holiday(
    body: HolidayCreateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: Session = Depends(get_db),
) -> HolidayResponse:
    return handle_create_holiday(access, db, body)


@router.patch("/holidays/{holiday_id}", response_model=HolidayResponse, status_code=status.HTTP_200_OK)
def update_holiday(
    holiday_id: str,
    body: HolidayUpdateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: Session = Depends(get_db),
) -> HolidayResponse:
    return handle_update_holiday(access, db, holiday_id, body)


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(
    holiday_id: str,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: Session = Depends(get_db),
) -> Response:
    handle_delete_holiday(access, db, holiday_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/requests", response_model=LeaveRequestListResponse, status_code=status.HTTP_200_OK)
def list_leave_requests(
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("view"))],
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status"),
    member_id: str | None = Query(default=None, alias="memberId"),
    leave_type_id: str | None = Query(default=None, alias="leaveTypeId"),
    from_date: dt.date | None = Query(default=None, alias="fromDate"),
    to_date: dt.date | None = Query(default=None, alias="toDate"),
    year: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> LeaveRequestListResponse:
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
    return handle_list_leave_requests(access, db, filters)


@router.get("/requests/{leave_request_id}", response_model=LeaveRequestResponse, status_code=status.HTTP_200_OK)
def get_leave_request(
    leave_request_id: str,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("view"))],
    db: Session = Depends(get_db),
) -> LeaveRequestResponse:
    return handle_get_leave_request(access, db, leave_request_id)


@router.post("/requests", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
def create_leave_request(
    body: LeaveRequestCreateRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("create"))],
    db: Session = Depends(get_db),
) -> LeaveRequestResponse:
    return handle_create_leave_request(access, db, body)


@router.post("/requests/{leave_request_id}/approve", response_model=LeaveRequestResponse, status_code=status.HTTP_200_OK)
def approve_leave_request(
    leave_request_id: str,
    body: LeaveRequestDecisionRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: Session = Depends(get_db),
) -> LeaveRequestResponse:
    return handle_approve_leave_request(access, db, leave_request_id, body)


@router.post("/requests/{leave_request_id}/reject", response_model=LeaveRequestResponse, status_code=status.HTTP_200_OK)
def reject_leave_request(
    leave_request_id: str,
    body: LeaveRequestDecisionRequest,
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("approve"))],
    db: Session = Depends(get_db),
) -> LeaveRequestResponse:
    return handle_reject_leave_request(access, db, leave_request_id, body)


@router.post("/requests/{leave_request_id}/cancel", response_model=LeaveRequestResponse, status_code=status.HTTP_200_OK)
def cancel_leave_request(
    leave_request_id: str,
    ctx: Annotated[MemberContext, Depends(get_member_context)],
    db: Session = Depends(get_db),
) -> LeaveRequestResponse:
    return handle_cancel_leave_request(ctx, db, leave_request_id)


@router.get("/balances", response_model=LeaveBalanceListResponse, status_code=status.HTTP_200_OK)
def list_leave_balances(
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("view"))],
    db: Session = Depends(get_db),
    year: int | None = Query(default=None),
    member_id: str | None = Query(default=None, alias="memberId"),
    leave_type_id: str | None = Query(default=None, alias="leaveTypeId"),
) -> LeaveBalanceListResponse:
    filters = LeaveBalanceFilters(year=year, member_id=member_id, leave_type_id=leave_type_id)
    return handle_list_leave_balances(access, db, filters)


@router.get("/calendar", response_model=LeaveCalendarResponse, status_code=status.HTTP_200_OK)
def get_leave_calendar(
    access: Annotated[LeaveAccessContext, Depends(require_leave_permission("view"))],
    db: Session = Depends(get_db),
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
    return handle_get_leave_calendar(access, db, filters)
