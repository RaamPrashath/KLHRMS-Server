"""
Attendance controller — thin orchestration layer.

Accepts validated schema inputs and resolved AttendanceAccessContext,
calls service functions, and returns response DTOs.
All HTTPException translation happens in the service layer; the controller
only maps ORM objects to response schemas.
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.modules.attendance.schema import (
    AttendanceListFilters,
    AttendanceListResponse,
    AttendanceRecordResponse,
    ClockInRequest,
    ClockOutRequest,
    DeleteDayEntryRequest,
    ManualDayEntryRequest,
)
from app.modules.attendance import service
from app.shared.deps.attendance_permissions import AttendanceAccessContext


def _to_response(record: object) -> AttendanceRecordResponse:
    return AttendanceRecordResponse.model_validate(record)


# ---------------------------------------------------------------------------
# Clock-in
# ---------------------------------------------------------------------------


def handle_clock_in(
    access: AttendanceAccessContext,
    db: Session,
    body: ClockInRequest,
) -> AttendanceRecordResponse:
    target_id = body.target_member_id or access.member.id

    # Validate target member belongs to the organization (unless self).
    if target_id != access.member.id:
        service.resolve_target_member(db, access.organization.id, target_id)

    record = service.clock_in(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=target_id,
        scope=access.permission_scope,
        clock_in_time=body.clock_in,
    )
    return _to_response(record)


# ---------------------------------------------------------------------------
# Clock-out
# ---------------------------------------------------------------------------


def handle_clock_out(
    access: AttendanceAccessContext,
    db: Session,
    body: ClockOutRequest,
) -> list[AttendanceRecordResponse]:
    target_id = body.target_member_id or access.member.id

    if target_id != access.member.id:
        service.resolve_target_member(db, access.organization.id, target_id)

    policy = service.load_policy(db, access.organization.id)

    records = service.clock_out(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=target_id,
        scope=access.permission_scope,
        policy=policy,
        clock_out_time=body.clock_out,
    )
    return [_to_response(r) for r in records]


# ---------------------------------------------------------------------------
# Manual day upsert
# ---------------------------------------------------------------------------


def handle_upsert_manual_day(
    access: AttendanceAccessContext,
    db: Session,
    body: ManualDayEntryRequest,
) -> AttendanceRecordResponse:
    service.resolve_target_member(db, access.organization.id, body.target_member_id)

    policy = service.load_policy(db, access.organization.id)

    record = service.upsert_manual_day(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=body.target_member_id,
        scope=access.permission_scope,
        policy=policy,
        day=body.entry_date,
        clock_in_time=body.clock_in,
        clock_out_time=body.clock_out,
    )
    return _to_response(record)


# ---------------------------------------------------------------------------
# Delete day entry
# ---------------------------------------------------------------------------


def handle_delete_day_entry(
    access: AttendanceAccessContext,
    db: Session,
    body: DeleteDayEntryRequest,
) -> None:
    service.resolve_target_member(db, access.organization.id, body.target_member_id)

    service.delete_day_entry(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=body.target_member_id,
        scope=access.permission_scope,
        day=body.entry_date,
    )


# ---------------------------------------------------------------------------
# Get my attendance
# ---------------------------------------------------------------------------


def handle_get_my_attendance(
    access: AttendanceAccessContext,
    db: Session,
    filters: AttendanceListFilters,
) -> AttendanceListResponse:
    items, total = service.get_my_attendance(
        db=db,
        organization_id=access.organization.id,
        member_id=access.member.id,
        date_from=filters.date_from,
        date_to=filters.date_to,
        status_filter=filters.status,
        page=filters.page,
        page_size=filters.page_size,
    )
    return AttendanceListResponse(
        items=[_to_response(r) for r in items],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


# ---------------------------------------------------------------------------
# List attendance
# ---------------------------------------------------------------------------


def handle_list_attendance(
    access: AttendanceAccessContext,
    db: Session,
    filters: AttendanceListFilters,
) -> AttendanceListResponse:
    items, total = service.list_attendance(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        scope=access.permission_scope,
        target_member_id=filters.target_member_id,
        date_from=filters.date_from,
        date_to=filters.date_to,
        status_filter=filters.status,
        page=filters.page,
        page_size=filters.page_size,
    )
    return AttendanceListResponse(
        items=[_to_response(r) for r in items],
        total=total,
        page=filters.page,
        page_size=filters.page_size,
    )


# ---------------------------------------------------------------------------
# Get attendance day
# ---------------------------------------------------------------------------


def handle_get_attendance_day(
    access: AttendanceAccessContext,
    db: Session,
    target_member_id: str,
    day: dt.date,
) -> AttendanceRecordResponse:
    service.resolve_target_member(db, access.organization.id, target_member_id)

    record = service.get_attendance_day(
        db=db,
        organization_id=access.organization.id,
        actor_member_id=access.member.id,
        target_member_id=target_member_id,
        scope=access.permission_scope,
        day=day,
    )
    return _to_response(record)
