"""
Attendance routes — FastAPI router.

All endpoints require:
  x-organization-slug  (resolved to Organization)
  x-membership-id      (resolved to Member + Role)

Permission enforcement is handled by require_attendance_permission(),
which returns an AttendanceAccessContext containing the resolved scope.

Supported permission scopes in this deployment:
  - "self"         → actor may only access their own records
  - "organization" → actor may access any member's records within the org

Unsupported scopes (team, department) are rejected with 403 because the
current schema has no team/department structure.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.modules.attendance.controller import (
    handle_clock_in,
    handle_clock_out,
    handle_delete_day_entry,
    handle_get_attendance_day,
    handle_get_my_attendance,
    handle_list_attendance,
    handle_upsert_manual_day,
)
from app.modules.attendance.schema import (
    AttendanceListFilters,
    AttendanceListResponse,
    AttendanceRecordResponse,
    ClockInRequest,
    ClockOutRequest,
    DeleteDayEntryRequest,
    ManualDayEntryRequest,
    AttendanceStatus,
)
from app.shared.database import get_db
from app.shared.deps.attendance_permissions import (
    AttendanceAccessContext,
    require_attendance_permission,
)

router = APIRouter(prefix="/attendance", tags=["attendance"])


# ---------------------------------------------------------------------------
# 1. Clock in
# ---------------------------------------------------------------------------


@router.post(
    "/clock-in",
    response_model=AttendanceRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Clock in",
    description=(
        "Open an attendance session for the target member. "
        "Defaults to the calling member if no target is supplied. "
        "Requires attendance.create permission."
    ),
)
def clock_in(
    body: ClockInRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("create")),
    ],
    db: Session = Depends(get_db),
) -> AttendanceRecordResponse:
    return handle_clock_in(access, db, body)


# ---------------------------------------------------------------------------
# 2. Clock out
# ---------------------------------------------------------------------------


@router.post(
    "/clock-out",
    response_model=list[AttendanceRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Clock out",
    description=(
        "Finalize the active attendance session. "
        "Applies 16-hour cap and splits across midnight if needed. "
        "Requires attendance.create permission."
    ),
)
def clock_out(
    body: ClockOutRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("create")),
    ],
    db: Session = Depends(get_db),
) -> list[AttendanceRecordResponse]:
    return handle_clock_out(access, db, body)


# ---------------------------------------------------------------------------
# 3. Manual day upsert
# ---------------------------------------------------------------------------


@router.post(
    "/day-entry",
    response_model=AttendanceRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Upsert manual day entry",
    description=(
        "Create or replace a single attendance day row for the target member. "
        "Sets enteredByManagerId to the calling member. "
        "Requires attendance.edit permission."
    ),
)
def upsert_day_entry(
    body: ManualDayEntryRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("edit")),
    ],
    db: Session = Depends(get_db),
) -> AttendanceRecordResponse:
    return handle_upsert_manual_day(access, db, body)


# ---------------------------------------------------------------------------
# 4. Delete day entry
# ---------------------------------------------------------------------------


@router.delete(
    "/day-entry",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete day entry",
    description=(
        "Delete a specific attendance row for the target member/date. "
        "Requires attendance.delete permission."
    ),
)
def delete_day_entry(
    body: DeleteDayEntryRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("delete")),
    ],
    db: Session = Depends(get_db),
) -> Response:
    handle_delete_day_entry(access, db, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 5. Get my attendance
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=AttendanceListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get my attendance",
    description=(
        "Return paginated attendance records for the calling member only. "
        "Never exposes other members' data. "
        "Requires attendance.view permission."
    ),
)
def get_my_attendance(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
    db: Session = Depends(get_db),
    date_from: dt.date | None = Query(default=None),
    date_to: dt.date | None = Query(default=None),
    status_filter: AttendanceStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> AttendanceListResponse:
    filters = AttendanceListFilters(
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return handle_get_my_attendance(access, db, filters)


# ---------------------------------------------------------------------------
# 6. List attendance
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=AttendanceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List attendance",
    description=(
        "Return paginated attendance records. "
        "Self-scope callers only see their own records. "
        "Organization-scope callers may filter by target_member_id. "
        "Requires attendance.view permission."
    ),
)
def list_attendance(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
    db: Session = Depends(get_db),
    target_member_id: str | None = Query(default=None),
    date_from: dt.date | None = Query(default=None),
    date_to: dt.date | None = Query(default=None),
    status_filter: AttendanceStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> AttendanceListResponse:
    filters = AttendanceListFilters(
        target_member_id=target_member_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return handle_list_attendance(access, db, filters)


# ---------------------------------------------------------------------------
# 7. Get attendance day
# ---------------------------------------------------------------------------


@router.get(
    "/day",
    response_model=AttendanceRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get attendance day",
    description=(
        "Fetch a single attendance row for the target member/date. "
        "Enforces self or organization scope. "
        "Requires attendance.view permission."
    ),
)
def get_attendance_day(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
    db: Session = Depends(get_db),
    target_member_id: str = Query(...),
    day: dt.date = Query(...),
) -> AttendanceRecordResponse:
    return handle_get_attendance_day(access, db, target_member_id, day)
