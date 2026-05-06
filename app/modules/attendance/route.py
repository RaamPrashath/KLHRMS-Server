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
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attendance.controller import (
    handle_clock_in,
    handle_clock_out,
    handle_delete_bulk_work_logs_day,
    handle_delete_day_entry,
    handle_get_attendance_day,
    handle_get_bulk_work_logs_day,
    handle_get_bulk_work_logs_range,
    handle_get_my_attendance,
    handle_list_attendance,
    handle_upsert_bulk_work_logs,
    handle_upsert_manual_day,
)
from app.modules.attendance.schema import (
    AttendanceListFilters,
    AttendanceListResponse,
    AttendanceRecordResponse,
    AttendanceStatus,
    BulkDaySingleResponse,
    BulkDeleteDayResponse,
    BulkRangeResponse,
    BulkUpsertRequest,
    BulkUpsertResponse,
    ClockInRequest,
    ClockOutRequest,
    DeleteDayEntryRequest,
    ManualDayEntryRequest,
)
from app.modules.attendance.export_schema import AttendanceExportRequest
from app.modules.attendance.export_service import (
    generate_csv,
    generate_csv_pivot,
    generate_pdf,
    generate_pdf_pivot,
    generate_xlsx,
    generate_xlsx_pivot,
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
async def clock_in(
    body: ClockInRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("create")),
    ],
    db: AsyncSession = Depends(get_db),
) -> AttendanceRecordResponse:
    return await handle_clock_in(access, db, body)


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
async def clock_out(
    body: ClockOutRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("create")),
    ],
    db: AsyncSession = Depends(get_db),
) -> list[AttendanceRecordResponse]:
    return await handle_clock_out(access, db, body)


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
async def upsert_day_entry(
    body: ManualDayEntryRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("edit")),
    ],
    db: AsyncSession = Depends(get_db),
) -> AttendanceRecordResponse:
    return await handle_upsert_manual_day(access, db, body)


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
async def delete_day_entry(
    body: DeleteDayEntryRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("delete")),
    ],
    db: AsyncSession = Depends(get_db),
) -> Response:
    await handle_delete_day_entry(access, db, body)
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
async def get_my_attendance(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
    db: AsyncSession = Depends(get_db),
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
    return await handle_get_my_attendance(access, db, filters)


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
        "Organization-scope callers may filter by target_member_id or employee_name. "
        "Requires attendance.view permission."
    ),
)
async def list_attendance(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
    db: AsyncSession = Depends(get_db),
    target_member_id: str | None = Query(default=None),
    employee_name: str | None = Query(default=None),
    date_from: dt.date | None = Query(default=None),
    date_to: dt.date | None = Query(default=None),
    status_filter: AttendanceStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> AttendanceListResponse:
    filters = AttendanceListFilters(
        target_member_id=target_member_id,
        employee_name=employee_name,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return await handle_list_attendance(access, db, filters)


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
async def get_attendance_day(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
    db: AsyncSession = Depends(get_db),
    target_member_id: str = Query(...),
    day: dt.date = Query(...),
) -> AttendanceRecordResponse:
    return await handle_get_attendance_day(access, db, target_member_id, day)


# ---------------------------------------------------------------------------
# 8. Upsert bulk work logs  POST /attendance/bulk-work-logs
# ---------------------------------------------------------------------------


@router.post(
    "/bulk-work-logs",
    response_model=BulkUpsertResponse,
    status_code=status.HTTP_200_OK,
    summary="Upsert bulk work logs",
    description=(
        "Save one or more days of bulk attendance work logs for the calling member. "
        "Each day replaces all existing logs for that date (overwrite semantics). "
        "An empty logs list for a day deletes that day's entry. "
        "Requires attendance.create permission."
    ),
)
async def upsert_bulk_work_logs(
    body: BulkUpsertRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("create")),
    ],
    db: AsyncSession = Depends(get_db),
) -> BulkUpsertResponse:
    return await handle_upsert_bulk_work_logs(access, db, body)


# ---------------------------------------------------------------------------
# 9. Get bulk attendance range  GET /attendance/bulk-work-logs
# ---------------------------------------------------------------------------


@router.get(
    "/bulk-work-logs",
    response_model=BulkRangeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get bulk attendance range",
    description=(
        "Fetch the calling member's attendance days and child work logs "
        "for a date range. Results are sorted by date ascending, logs by "
        "startTime ascending. "
        "Requires attendance.view permission."
    ),
)
async def get_bulk_work_logs_range(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
    db: AsyncSession = Depends(get_db),
    date_from: dt.date = Query(..., alias="from", description="Inclusive start date (YYYY-MM-DD)."),
    date_to: dt.date = Query(..., alias="to", description="Inclusive end date (YYYY-MM-DD)."),
) -> BulkRangeResponse:
    if date_to < date_from:
        from fastapi import HTTPException as _HTTPException
        raise _HTTPException(status_code=422, detail="'to' must be >= 'from'")
    return await handle_get_bulk_work_logs_range(access, db, date_from, date_to)


# ---------------------------------------------------------------------------
# 10. Get one day detail  GET /attendance/bulk-work-logs/day
# ---------------------------------------------------------------------------


@router.get(
    "/bulk-work-logs/day",
    response_model=BulkDaySingleResponse,
    status_code=status.HTTP_200_OK,
    summary="Get one day's bulk attendance detail",
    description=(
        "Fetch one date's attendance record and all child work logs "
        "for the calling member. Returns day: null if no entry exists. "
        "Requires attendance.view permission."
    ),
)
async def get_bulk_work_logs_day(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
    db: AsyncSession = Depends(get_db),
    day: dt.date = Query(..., description="Calendar date to fetch (YYYY-MM-DD)."),
) -> BulkDaySingleResponse:
    return await handle_get_bulk_work_logs_day(access, db, day)


# ---------------------------------------------------------------------------
# 11. Delete one day bulk entry  DELETE /attendance/bulk-work-logs/day
# ---------------------------------------------------------------------------


@router.delete(
    "/bulk-work-logs/day",
    response_model=BulkDeleteDayResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete one day's bulk attendance entry",
    description=(
        "Delete the calling member's attendance record and all child work logs "
        "for the specified date. Returns 404 if no entry exists. "
        "Requires attendance.delete permission."
    ),
)
async def delete_bulk_work_logs_day(
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("delete")),
    ],
    db: AsyncSession = Depends(get_db),
    day: dt.date = Query(..., description="Calendar date to delete (YYYY-MM-DD)."),
) -> BulkDeleteDayResponse:
    return await handle_delete_bulk_work_logs_day(access, db, day)


# ---------------------------------------------------------------------------
# 12. Export attendance  POST /attendance/export
# ---------------------------------------------------------------------------

_MIME_TYPES: dict[str, str] = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "csv": "text/csv; charset=utf-8",
}

_FILE_EXTENSIONS: dict[str, str] = {
    "xlsx": "xlsx",
    "pdf": "pdf",
    "csv": "csv",
}


@router.post(
    "/export",
    status_code=status.HTTP_200_OK,
    summary="Export attendance records",
    description=(
        "Generate an Excel, PDF, or CSV file from the currently visible "
        "attendance records sent by the frontend. "
        "Requires attendance.view permission."
    ),
)
def export_attendance(
    body: AttendanceExportRequest,
    access: Annotated[
        AttendanceAccessContext,
        Depends(require_attendance_permission("view")),
    ],
) -> StreamingResponse:
    fmt = body.format

    if body.exportMode == "pivot":
        if body.pivotData is None:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(status_code=422, detail="pivotData is required for pivot export")
        if fmt == "xlsx":
            content = generate_xlsx_pivot(body.pivotData, body.title)
        elif fmt == "pdf":
            content = generate_pdf_pivot(body.pivotData, body.title)
        else:
            content = generate_csv_pivot(body.pivotData)
    else:
        if not body.records:
            from fastapi import HTTPException as _HTTPException
            raise _HTTPException(status_code=422, detail="records is required for list export")
        if fmt == "xlsx":
            content = generate_xlsx(body.records, body.showEmployeeColumn, body.title)
        elif fmt == "pdf":
            content = generate_pdf(body.records, body.showEmployeeColumn, body.title)
        else:
            content = generate_csv(body.records, body.showEmployeeColumn)

    import io
    filename = f"attendance.{_FILE_EXTENSIONS[fmt]}"

    return StreamingResponse(
        io.BytesIO(content),
        media_type=_MIME_TYPES[fmt],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )
