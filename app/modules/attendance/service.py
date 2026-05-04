"""
Attendance service — core business logic.

Key design decisions:
  - AttendanceRecord.employeeId maps to Member.id in this codebase.
  - Active open session = a row where clockIn is not null and clockOut is null.
  - Sessions crossing midnight are split into per-day rows.
  - Sessions exceeding 16 hours are hard-capped at 16 hours.
  - One row per (employeeId, date) — upsert/replace semantics.
  - Only "self" and "organization" scopes are enforced; "team"/"department"
    are rejected upstream in the permission dependency.
  - WorkHourPolicy is loaded per organization; defaults are used if absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.attendance_record import AttendanceRecord
from app.models.base import generate_uuid
from app.models.member import Member
from app.models.work_hour_policy import WorkHourPolicy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SESSION_HOURS: float = 16.0

# Defaults used when no WorkHourPolicy row exists for the organization.
_DEFAULT_STANDARD_HOURS: float = 8.0
_DEFAULT_OVERTIME_THRESHOLD: float = 8.0
_DEFAULT_HALF_DAY_MAX_HOURS: float = 4.0


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class PolicyDefaults:
    standard_hours_per_day: float
    overtime_threshold: float
    half_day_max_hours: float


@dataclass
class DaySegment:
    """A bounded clock session for a single calendar day."""

    day: date
    clock_in: datetime
    clock_out: datetime


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------


def load_policy(db: Session, organization_id: str) -> PolicyDefaults:
    """
    Load WorkHourPolicy for the organization.
    Falls back to safe defaults if no policy row exists.
    Only the three fields relevant to attendance are used:
      - standardHoursPerDay
      - overtimeThreshold
      - halfDayMaxHours
    """
    policy: WorkHourPolicy | None = (
        db.query(WorkHourPolicy)
        .filter(WorkHourPolicy.organizationId == organization_id)
        .first()
    )
    if policy is None:
        return PolicyDefaults(
            standard_hours_per_day=_DEFAULT_STANDARD_HOURS,
            overtime_threshold=_DEFAULT_OVERTIME_THRESHOLD,
            half_day_max_hours=_DEFAULT_HALF_DAY_MAX_HOURS,
        )
    return PolicyDefaults(
        standard_hours_per_day=policy.standardHoursPerDay,
        overtime_threshold=policy.overtimeThreshold,
        half_day_max_hours=policy.halfDayMaxHours,
    )


# ---------------------------------------------------------------------------
# Calculation helpers
# ---------------------------------------------------------------------------


def _compute_hours(clock_in: datetime, clock_out: datetime) -> float:
    """Return total hours between two datetimes, rounded to 4 decimal places."""
    delta = clock_out - clock_in
    return round(delta.total_seconds() / 3600, 4)


def _compute_overtime(total_hours: float, threshold: float) -> float:
    """Return overtime hours (0 if under threshold)."""
    return round(max(0.0, total_hours - threshold), 4)


def _derive_status(total_hours: float, half_day_max: float) -> str:
    """
    Derive attendance status from total hours.
      - total_hours <= half_day_max  → HALF_DAY
      - total_hours > half_day_max   → PRESENT
    ABSENT is only set explicitly (e.g. manual entry with no clock data).
    """
    if total_hours <= half_day_max:
        return "HALF_DAY"
    return "PRESENT"


def _cap_clock_out(clock_in: datetime, clock_out: datetime) -> datetime:
    """
    Enforce the 16-hour hard cap.
    Returns clock_out unchanged if within the cap, otherwise returns
    clock_in + 16 hours.
    """
    max_out = clock_in + timedelta(hours=MAX_SESSION_HOURS)
    return min(clock_out, max_out)


def _split_into_day_segments(clock_in: datetime, clock_out: datetime) -> list[DaySegment]:
    """
    Split a clock session that may span multiple calendar days into
    per-day DaySegment objects.

    Each segment is bounded by midnight boundaries in UTC.
    The 16-hour cap is applied to the total session before splitting.
    """
    # Ensure both datetimes are timezone-aware (UTC).
    if clock_in.tzinfo is None:
        clock_in = clock_in.replace(tzinfo=timezone.utc)
    if clock_out.tzinfo is None:
        clock_out = clock_out.replace(tzinfo=timezone.utc)

    # Apply 16-hour cap to the full session.
    clock_out = _cap_clock_out(clock_in, clock_out)

    segments: list[DaySegment] = []
    current_start = clock_in

    while True:
        current_day = current_start.date()
        # Midnight at the end of the current calendar day (UTC).
        next_midnight = datetime(
            current_day.year,
            current_day.month,
            current_day.day,
            tzinfo=timezone.utc,
        ) + timedelta(days=1)

        if clock_out <= next_midnight:
            # Session ends within the current day.
            segments.append(
                DaySegment(
                    day=current_day,
                    clock_in=current_start,
                    clock_out=clock_out,
                )
            )
            break
        else:
            # Session crosses midnight — take the portion up to midnight.
            segments.append(
                DaySegment(
                    day=current_day,
                    clock_in=current_start,
                    clock_out=next_midnight,
                )
            )
            current_start = next_midnight

    return segments


# ---------------------------------------------------------------------------
# Member resolution helpers
# ---------------------------------------------------------------------------


def resolve_target_member(
    db: Session,
    organization_id: str,
    target_member_id: str,
) -> Member:
    """
    Verify that a Member exists and belongs to the given organization.
    Raises 404 if not found, 403 if outside the organization.
    """
    member: Member | None = (
        db.query(Member)
        .filter(Member.id == target_member_id)
        .first()
    )
    if member is None:
        raise HTTPException(status_code=404, detail="Target member not found")
    if member.organizationId != organization_id:
        raise HTTPException(
            status_code=403,
            detail="Target member does not belong to this organization",
        )
    return member


def enforce_scope(
    actor_member_id: str,
    target_member_id: str,
    scope: str,
) -> None:
    """
    Enforce self vs organization scope.

    - "self": target must equal actor.
    - "organization": any member in the same org is allowed (org membership
      is already validated by resolve_target_member).
    - Anything else is rejected (should have been caught upstream, but
      this is a safety net).
    """
    if scope == "self" and target_member_id != actor_member_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own attendance records",
        )
    if scope not in ("self", "organization"):
        raise HTTPException(
            status_code=403,
            detail=f"Attendance scope '{scope}' is not supported",
        )


# ---------------------------------------------------------------------------
# Active session detection
# ---------------------------------------------------------------------------


def get_active_session(
    db: Session,
    organization_id: str,
    employee_id: str,
) -> AttendanceRecord | None:
    """
    Return the open attendance row for the given member (clockIn set, clockOut null).
    Returns None if no active session exists.
    """
    return (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == employee_id,
            AttendanceRecord.clockIn.isnot(None),
            AttendanceRecord.clockOut.is_(None),
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Upsert helper
# ---------------------------------------------------------------------------


def _upsert_day_row(
    db: Session,
    organization_id: str,
    employee_id: str,
    day: date,
    clock_in: datetime | None,
    clock_out: datetime | None,
    total_hours: float | None,
    overtime_hours: float | None,
    status: str,
    entered_by_manager_id: str | None,
) -> AttendanceRecord:
    """
    Create or replace the attendance row for (employeeId, date).
    This is the single write path for all attendance mutations.
    """
    existing: AttendanceRecord | None = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == employee_id,
            AttendanceRecord.date == day,
        )
        .first()
    )

    if existing is not None:
        existing.clockIn = clock_in
        existing.clockOut = clock_out
        existing.totalHours = total_hours
        existing.overtimeHours = overtime_hours
        existing.status = status
        existing.enteredByManagerId = entered_by_manager_id
        record = existing
    else:
        record = AttendanceRecord(
            id=generate_uuid(),
            employeeId=employee_id,
            organizationId=organization_id,
            date=day,
            clockIn=clock_in,
            clockOut=clock_out,
            totalHours=total_hours,
            overtimeHours=overtime_hours,
            status=status,
            enteredByManagerId=entered_by_manager_id,
        )
        db.add(record)

    try:
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Attendance record conflict for this member/date",
        )
    return record


# ---------------------------------------------------------------------------
# Clock-in
# ---------------------------------------------------------------------------


def clock_in(
    db: Session,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    clock_in_time: datetime | None = None,
) -> AttendanceRecord:
    """
    Open an attendance session for the target member.

    - Validates scope.
    - Rejects duplicate active clock-in.
    - Creates/updates the current-day row with clockIn set and status PRESENT.
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    # Reject if there is already an open session.
    active = get_active_session(db, organization_id, target_member_id)
    if active is not None:
        raise HTTPException(
            status_code=400,
            detail="An active clock-in session already exists for this member",
        )

    now = clock_in_time or datetime.now(tz=timezone.utc)
    today = now.date()

    return _upsert_day_row(
        db=db,
        organization_id=organization_id,
        employee_id=target_member_id,
        day=today,
        clock_in=now,
        clock_out=None,
        total_hours=None,
        overtime_hours=None,
        status="PRESENT",
        entered_by_manager_id=None,
    )


# ---------------------------------------------------------------------------
# Clock-out
# ---------------------------------------------------------------------------


def clock_out(
    db: Session,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    policy: PolicyDefaults,
    clock_out_time: datetime | None = None,
) -> list[AttendanceRecord]:
    """
    Finalize an open attendance session.

    - Validates scope.
    - Resolves the active open session.
    - Applies 16-hour cap.
    - Splits across midnight if needed.
    - Computes totals, overtime, and status for each day segment.
    - Upserts all affected day rows.

    Returns the list of written AttendanceRecord rows (usually one, but
    may be multiple if the session crossed midnight).
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    active = get_active_session(db, organization_id, target_member_id)
    if active is None:
        raise HTTPException(
            status_code=400,
            detail="No active clock-in session found for this member",
        )

    now = clock_out_time or datetime.now(tz=timezone.utc)

    # Ensure clock_in is timezone-aware.
    ci = active.clockIn
    if ci.tzinfo is None:
        ci = ci.replace(tzinfo=timezone.utc)

    if now <= ci:
        raise HTTPException(
            status_code=400,
            detail="clock_out must be after clock_in",
        )

    segments = _split_into_day_segments(ci, now)
    written: list[AttendanceRecord] = []

    for seg in segments:
        total = _compute_hours(seg.clock_in, seg.clock_out)
        overtime = _compute_overtime(total, policy.overtime_threshold)
        status = _derive_status(total, policy.half_day_max_hours)

        record = _upsert_day_row(
            db=db,
            organization_id=organization_id,
            employee_id=target_member_id,
            day=seg.day,
            clock_in=seg.clock_in,
            clock_out=seg.clock_out,
            total_hours=total,
            overtime_hours=overtime,
            status=status,
            entered_by_manager_id=None,
        )
        written.append(record)

    return written


# ---------------------------------------------------------------------------
# Manual day upsert
# ---------------------------------------------------------------------------


def upsert_manual_day(
    db: Session,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    policy: PolicyDefaults,
    day: date,
    clock_in_time: datetime | None,
    clock_out_time: datetime | None,
) -> AttendanceRecord:
    """
    Manually create or replace a single attendance day row.

    - Validates scope.
    - Recomputes totals/status/overtime from provided clock times.
    - Sets enteredByManagerId to the actor.
    - Overwrites any existing row for that member/date.
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    total_hours: float | None = None
    overtime_hours: float | None = None
    status = "ABSENT"

    if clock_in_time is not None and clock_out_time is not None:
        # Ensure timezone-aware.
        ci = clock_in_time if clock_in_time.tzinfo else clock_in_time.replace(tzinfo=timezone.utc)
        co = clock_out_time if clock_out_time.tzinfo else clock_out_time.replace(tzinfo=timezone.utc)

        if co <= ci:
            raise HTTPException(
                status_code=400,
                detail="clock_out must be after clock_in",
            )

        total_hours = _compute_hours(ci, co)
        overtime_hours = _compute_overtime(total_hours, policy.overtime_threshold)
        status = _derive_status(total_hours, policy.half_day_max_hours)
    elif clock_in_time is not None:
        # Open session — mark PRESENT, no totals yet.
        status = "PRESENT"

    return _upsert_day_row(
        db=db,
        organization_id=organization_id,
        employee_id=target_member_id,
        day=day,
        clock_in=clock_in_time,
        clock_out=clock_out_time,
        total_hours=total_hours,
        overtime_hours=overtime_hours,
        status=status,
        entered_by_manager_id=actor_member_id,
    )


# ---------------------------------------------------------------------------
# Delete day entry
# ---------------------------------------------------------------------------


def delete_day_entry(
    db: Session,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    day: date,
) -> None:
    """
    Delete a specific attendance row for the target member/date.
    Raises 404 if the row does not exist.
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    record: AttendanceRecord | None = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == target_member_id,
            AttendanceRecord.date == day,
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    db.delete(record)
    db.commit()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_my_attendance(
    db: Session,
    organization_id: str,
    member_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AttendanceRecord], int]:
    """
    Return paginated attendance rows for the calling member only.
    Never exposes other members' data.
    """
    q = db.query(AttendanceRecord).filter(
        AttendanceRecord.organizationId == organization_id,
        AttendanceRecord.employeeId == member_id,
    )
    if date_from is not None:
        q = q.filter(AttendanceRecord.date >= date_from)
    if date_to is not None:
        q = q.filter(AttendanceRecord.date <= date_to)
    if status_filter is not None:
        q = q.filter(AttendanceRecord.status == status_filter)

    total = q.count()
    items = (
        q.order_by(AttendanceRecord.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def list_attendance(
    db: Session,
    organization_id: str,
    actor_member_id: str,
    scope: str,
    target_member_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AttendanceRecord], int]:
    """
    Return paginated attendance rows respecting scope.

    - "self": always filters to actor's own records, ignores target_member_id.
    - "organization": allows filtering by target_member_id or listing all org records.
    """
    q = db.query(AttendanceRecord).filter(
        AttendanceRecord.organizationId == organization_id,
    )

    if scope == "self":
        q = q.filter(AttendanceRecord.employeeId == actor_member_id)
    elif scope == "organization":
        if target_member_id is not None:
            q = q.filter(AttendanceRecord.employeeId == target_member_id)
    # No team/department filtering — not supported in current schema.

    if date_from is not None:
        q = q.filter(AttendanceRecord.date >= date_from)
    if date_to is not None:
        q = q.filter(AttendanceRecord.date <= date_to)
    if status_filter is not None:
        q = q.filter(AttendanceRecord.status == status_filter)

    total = q.count()
    items = (
        q.order_by(AttendanceRecord.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_attendance_day(
    db: Session,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    day: date,
) -> AttendanceRecord:
    """
    Fetch a single attendance row for the target member/date.
    Enforces scope and raises 404 if not found.
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    record: AttendanceRecord | None = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == target_member_id,
            AttendanceRecord.date == day,
        )
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return record


# ---------------------------------------------------------------------------
# Auto-stop helper (internal)
# ---------------------------------------------------------------------------


def auto_stop_open_sessions(
    db: Session,
    organization_id: str,
    policy: PolicyDefaults,
) -> list[AttendanceRecord]:
    """
    Find all open sessions in the organization that have exceeded 16 hours
    and hard-stop them at exactly clock_in + 16 hours.

    This is an internal helper — it is not exposed as a public route.
    Splits across midnight if the 16-hour boundary crosses a day boundary.

    Returns the list of all written records.
    """
    now = datetime.now(tz=timezone.utc)
    cutoff = now - timedelta(hours=MAX_SESSION_HOURS)

    open_sessions: list[AttendanceRecord] = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.clockIn.isnot(None),
            AttendanceRecord.clockOut.is_(None),
            AttendanceRecord.clockIn <= cutoff,
        )
        .all()
    )

    written: list[AttendanceRecord] = []
    for session in open_sessions:
        ci = session.clockIn
        if ci.tzinfo is None:
            ci = ci.replace(tzinfo=timezone.utc)

        hard_stop = ci + timedelta(hours=MAX_SESSION_HOURS)
        segments = _split_into_day_segments(ci, hard_stop)

        for seg in segments:
            total = _compute_hours(seg.clock_in, seg.clock_out)
            overtime = _compute_overtime(total, policy.overtime_threshold)
            status = _derive_status(total, policy.half_day_max_hours)

            record = _upsert_day_row(
                db=db,
                organization_id=organization_id,
                employee_id=session.employeeId,
                day=seg.day,
                clock_in=seg.clock_in,
                clock_out=seg.clock_out,
                total_hours=total,
                overtime_hours=overtime,
                status=status,
                entered_by_manager_id=None,
            )
            written.append(record)

    return written
