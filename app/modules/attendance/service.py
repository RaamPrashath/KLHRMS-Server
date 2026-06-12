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
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_work_log import AttendanceWorkLog
from app.models.base import generate_uuid
from app.models.department import Department
from app.models.department_member import DepartmentMember
from app.models.member import Member
from app.models.project import Project
from app.models.project_task import ProjectTask
from app.models.user import User
from app.models.weekly_plan import WeeklyPlan
from app.models.work_hour_policy import WorkHourPolicy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SESSION_HOURS: float = 16.0
BUSINESS_TIMEZONE = timezone(timedelta(hours=5, minutes=30))

# Defaults used when no WorkHourPolicy row exists for the organization.
_DEFAULT_STANDARD_HOURS: float = 8.0
_DEFAULT_OVERTIME_THRESHOLD: float = 8.0
_DEFAULT_HALF_DAY_MAX_HOURS: float = 4.0
_NON_WORKING_PLAN_LOCATIONS: frozenset[str] = frozenset({"HOLIDAY"})


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


@dataclass(frozen=True)
class LocationValidationResult:
    actual_location: str
    distance_meters: float | None


@dataclass
class WorkLogReportSummaryData:
    total_days: int
    total_hours: float
    employee_count: int


@dataclass
class WorkLogReportRowData:
    attendance_record_id: str
    employee_id: str
    employee_name: str
    employee_email: str | None
    day: date
    clock_in: datetime | None
    clock_out: datetime | None
    total_hours: float | None
    department_name: str | None
    project_name: str | None
    task_name: str | None
    daily_work_log: str | None


def _display_employee_name(
    raw_name: str | None,
    email: str | None,
    fallback_id: str,
) -> str:
    normalized_name = (raw_name or "").strip()
    normalized_email = (email or "").strip()

    if normalized_name and normalized_name.lower() != normalized_email.lower():
        return normalized_name

    if normalized_email:
        local_part = normalized_email.split("@", 1)[0].strip()
        if local_part:
            prettified = re.sub(r"[._-]+", " ", local_part).strip()
            if prettified:
                return " ".join(part.capitalize() for part in prettified.split())
        return normalized_email

    return fallback_id


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------


async def load_policy(db: AsyncSession, organization_id: str) -> PolicyDefaults:
    """
    Load WorkHourPolicy for the organization.
    Falls back to safe defaults if no policy row exists.
    Only the three fields relevant to attendance are used:
      - standardHoursPerDay
      - overtimeThreshold
      - halfDayMaxHours
    """
    result = await db.execute(
        select(WorkHourPolicy).where(WorkHourPolicy.organizationId == organization_id)
    )
    policy: WorkHourPolicy | None = result.scalar_one_or_none()
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


def _normalize_attendance_datetime(value: datetime) -> datetime:
    """
    Return a timezone-aware datetime.

    Some attendance rows can come back from the DB as naive local business time.
    Treating those as UTC makes clock-in appear several hours in the future,
    which freezes the timer and makes clock-out fail.
    """
    if value.tzinfo is not None:
        return value

    as_utc = value.replace(tzinfo=timezone.utc)
    if as_utc > datetime.now(tz=timezone.utc) + timedelta(minutes=1):
        return value.replace(tzinfo=BUSINESS_TIMEZONE)
    return as_utc


def _to_radians(value: float) -> float:
    from math import pi

    return value * pi / 180.0


def _haversine_distance_meters(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    from math import asin, cos, sin, sqrt

    earth_radius_meters = 6_371_000.0
    lat_a = _to_radians(latitude_a)
    lat_b = _to_radians(latitude_b)
    delta_lat = _to_radians(latitude_b - latitude_a)
    delta_lng = _to_radians(longitude_b - longitude_a)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat_a) * cos(lat_b) * sin(delta_lng / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return earth_radius_meters * c


def _validate_clock_in_location(
    declared_location: str,
    latitude: float,
    longitude: float,
    office_latitude: float | None,
    office_longitude: float | None,
    office_radius_meters: float,
) -> LocationValidationResult:
    if office_latitude is None or office_longitude is None:
        return LocationValidationResult(
            actual_location=declared_location,
            distance_meters=None,
        )

    distance_meters = _haversine_distance_meters(
        latitude,
        longitude,
        office_latitude,
        office_longitude,
    )
    actual_location = "OFFICE" if distance_meters <= office_radius_meters else "REMOTE"

    if declared_location != actual_location:
        expected_label = "office" if actual_location == "OFFICE" else "remote"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Clock-in location mismatch. Your coordinates indicate {expected_label} "
                f"attendance, so select {expected_label.title()} to continue."
            ),
        )

    return LocationValidationResult(
        actual_location=actual_location,
        distance_meters=round(distance_meters, 2),
    )


async def _get_weekly_plan_location_for_day(
    db: AsyncSession,
    organization_id: str,
    user_id: str,
    day: date,
) -> str | None:
    result = await db.execute(
        select(WeeklyPlan.work_location).where(
            WeeklyPlan.organization_id == uuid.UUID(organization_id),
            WeeklyPlan.user_id == user_id,
            WeeklyPlan.date == day,
            WeeklyPlan.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


def _actual_location_to_plan_value(actual_location: str) -> str:
    return "WFH" if actual_location == "REMOTE" else "OFFICE"


async def _sync_weekly_plan_location_for_clock_in(
    db: AsyncSession,
    organization_id: str,
    user_id: str,
    day: date,
    actual_location: str,
    commit: bool = True,
) -> None:
    actual_plan_value = _actual_location_to_plan_value(actual_location)
    wp_result = await db.execute(
        select(WeeklyPlan).where(
            WeeklyPlan.organization_id == uuid.UUID(organization_id),
            WeeklyPlan.user_id == user_id,
            WeeklyPlan.date == day,
            WeeklyPlan.deleted_at.is_(None),
        )
    )
    wp_entry: WeeklyPlan | None = wp_result.scalar_one_or_none()
    if wp_entry is None or wp_entry.work_location == actual_plan_value:
        return

    wp_entry.work_location = actual_plan_value
    if commit:
        await db.commit()
    else:
        await db.flush()


async def _check_day_has_approved_leave(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    day: date,
) -> bool:
    """Return True if the member has an approved leave request covering this day."""
    from app.models.leave import LeaveRequest
    from app.shared.utils.enums import LeaveRequestStatus

    result = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.organizationId == organization_id,
            LeaveRequest.memberId == member_id,
            LeaveRequest.deletedAt.is_(None),
            LeaveRequest.status == LeaveRequestStatus.APPROVED,
            LeaveRequest.startDate <= day,
            LeaveRequest.endDate >= day,
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


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

    Each segment is bounded by midnight boundaries in the business timezone.
    The 16-hour cap is applied to the total session before splitting.
    """
    clock_in = _normalize_attendance_datetime(clock_in).astimezone(BUSINESS_TIMEZONE)
    clock_out = _normalize_attendance_datetime(clock_out).astimezone(BUSINESS_TIMEZONE)

    # Apply 16-hour cap to the full session.
    clock_out = _cap_clock_out(clock_in, clock_out)

    segments: list[DaySegment] = []
    current_start = clock_in

    while True:
        current_day = current_start.date()
        # Midnight at the end of the current business day.
        next_midnight = datetime(
            current_day.year,
            current_day.month,
            current_day.day,
            tzinfo=BUSINESS_TIMEZONE,
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


async def resolve_target_member(
    db: AsyncSession,
    organization_id: str,
    target_member_id: str,
) -> Member:
    """
    Verify that a Member exists and belongs to the given organization.
    Raises 404 if not found, 403 if outside the organization.
    """
    result = await db.execute(
        select(Member).where(Member.id == target_member_id)
    )
    member: Member | None = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Target member not found")
    if member.organizationId != organization_id:
        raise HTTPException(
            status_code=403,
            detail="Target member does not belong to this organization",
        )
    return member


async def _validate_attendance_project_selection(
    db: AsyncSession,
    organization_id: str,
    project_id: str | None,
    project_task_id: str | None,
) -> tuple[str | None, str | None]:
    """
    Validate project/task pairing used by attendance and work logs.

    - Both values may be omitted.
    - If one is provided, both are required.
    - Project must belong to the organization and remain active.
    - Task must belong to the selected project.
    """
    normalized_project_id = project_id.strip() if project_id else None
    normalized_task_id = project_task_id.strip() if project_task_id else None

    if normalized_project_id is None and normalized_task_id is None:
        return None, None

    if normalized_project_id is None or normalized_task_id is None:
        raise HTTPException(
            status_code=422,
            detail="Both project_id and project_task_id are required together",
        )

    project_result = await db.execute(
        select(Project).where(
            Project.id == normalized_project_id,
            Project.organizationId == organization_id,
            Project.status == "ACTIVE",
            Project.deletedAt.is_(None),
        )
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    task_result = await db.execute(
        select(ProjectTask).where(
            ProjectTask.id == normalized_task_id,
            ProjectTask.projectId == normalized_project_id,
        )
    )
    task = task_result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Project task not found")

    return normalized_project_id, normalized_task_id


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


async def get_active_session(
    db: AsyncSession,
    organization_id: str,
    employee_id: str,
) -> AttendanceRecord | None:
    """
    Return the open attendance row for the given member (clockIn set, clockOut null).
    Returns None if no active session exists.
    """
    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == employee_id,
            AttendanceRecord.clockIn.isnot(None),
            AttendanceRecord.clockOut.is_(None),
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Upsert helper
# ---------------------------------------------------------------------------


async def _upsert_day_row(
    db: AsyncSession,
    organization_id: str,
    employee_id: str,
    day: date,
    clock_in: datetime | None,
    clock_out: datetime | None,
    total_hours: float | None,
    overtime_hours: float | None,
    status: str,
    entered_by_manager_id: str | None,
    project_id: str | None = None,
    project_task_id: str | None = None,
    description: str | None = None,
    is_remote: bool = False,
    entry_type: str | None = None,
    commit: bool = True,
) -> AttendanceRecord:
    """
    Create or replace the attendance row for (employeeId, date).
    This is the single write path for all attendance mutations.
    """
    existing_result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == employee_id,
            AttendanceRecord.date == day,
        )
    )
    existing: AttendanceRecord | None = existing_result.scalar_one_or_none()

    if existing is not None:
        existing.clockIn = clock_in
        existing.clockOut = clock_out
        existing.projectId = project_id
        existing.projectTaskId = project_task_id
        existing.description = description
        existing.totalHours = total_hours
        existing.overtimeHours = overtime_hours
        existing.status = status
        existing.enteredByManagerId = entered_by_manager_id
        existing.isRemote = is_remote
        existing.entryType = entry_type
        record = existing
    else:
        record = AttendanceRecord(
            id=generate_uuid(),
            employeeId=employee_id,
            organizationId=organization_id,
            date=day,
            clockIn=clock_in,
            clockOut=clock_out,
            projectId=project_id,
            projectTaskId=project_task_id,
            description=description,
            totalHours=total_hours,
            overtimeHours=overtime_hours,
            status=status,
            enteredByManagerId=entered_by_manager_id,
            isRemote=is_remote,
            entryType=entry_type,
        )
        db.add(record)

    try:
        if commit:
            await db.commit()
        else:
            await db.flush()
        await db.refresh(record)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Attendance record conflict for this member/date",
        )
    return record


# ---------------------------------------------------------------------------
# Clock-in
# ---------------------------------------------------------------------------


async def clock_in(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    clock_in_time: datetime | None = None,
    work_location: str = "OFFICE",
    latitude: float = 0,
    longitude: float = 0,
    accuracy_meters: float | None = None,
    project_id: str | None = None,
    project_task_id: str | None = None,
    description: str | None = None,
    office_latitude: float | None = None,
    office_longitude: float | None = None,
    office_radius_meters: float = 200.0,
) -> AttendanceRecord:
    """
    Open an attendance session for the target member.

    - Validates scope.
    - Rejects duplicate active clock-in.
    - Creates/updates the current-day row with clockIn set and status PRESENT.
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    now = (
        _normalize_attendance_datetime(clock_in_time)
        if clock_in_time is not None
        else datetime.now(tz=BUSINESS_TIMEZONE)
    )
    today = now.astimezone(BUSINESS_TIMEZONE).date()

    # Reject if there is already an open session.
    active = await get_active_session(db, organization_id, target_member_id)
    if active is not None:
        if active.date >= today:
            # Same-day or future session — genuine duplicate.
            raise HTTPException(
                status_code=400,
                detail="An active clock-in session already exists for this member",
            )

        # Stale session from a previous day — auto-close at 23:50 same day and proceed.
        ci = _normalize_attendance_datetime(active.clockIn).astimezone(BUSINESS_TIMEZONE)
        close_time = datetime(
            active.date.year, active.date.month, active.date.day, 23, 50,
            tzinfo=BUSINESS_TIMEZONE,
        )
        clock_out = _cap_clock_out(ci, close_time)
        stale_total = _compute_hours(ci, clock_out)

        policy = await load_policy(db, organization_id)
        stale_overtime = _compute_overtime(stale_total, policy.overtime_threshold)
        stale_status = _derive_status(stale_total, policy.half_day_max_hours)

        active.clockOut = clock_out
        active.totalHours = stale_total
        active.overtimeHours = stale_overtime
        active.status = stale_status
        await db.flush()
    validated_project_id, validated_project_task_id = await _validate_attendance_project_selection(
        db=db,
        organization_id=organization_id,
        project_id=project_id,
        project_task_id=project_task_id,
    )
    normalized_description = description.strip() if description else None
    target_member = await resolve_target_member(db, organization_id, target_member_id)
    validation_result = _validate_clock_in_location(
        declared_location=work_location,
        latitude=latitude,
        longitude=longitude,
        office_latitude=office_latitude,
        office_longitude=office_longitude,
        office_radius_meters=office_radius_meters,
    )
    planned_location = await _get_weekly_plan_location_for_day(
        db=db,
        organization_id=organization_id,
        user_id=target_member.userId,
        day=today,
    )
    if planned_location in _NON_WORKING_PLAN_LOCATIONS:
        raise HTTPException(
            status_code=400,
            detail="Today's weekly plan blocks clock-in for this day.",
        )

    record = await _upsert_day_row(
        db=db,
        organization_id=organization_id,
        employee_id=target_member_id,
        day=today,
        clock_in=now,
        clock_out=None,
        project_id=validated_project_id,
        project_task_id=validated_project_task_id,
        description=normalized_description,
        total_hours=None,
        overtime_hours=None,
        status="PRESENT",
        entered_by_manager_id=None,
        is_remote=(validation_result.actual_location == "REMOTE"),
        commit=False,
    )

    # ── If today was a leave day, restore quota + update plan ───────────
    if await _check_day_has_approved_leave(db, organization_id, target_member_id, today):
        from app.models.leave import LeaveBalance as _LeaveBalance
        from app.models.leave import LeaveRequest as _LeaveRequest
        from app.shared.utils.enums import LeaveRequestStatus as _LeaveRequestStatus

        # Fetch approved leave requests covering today
        leave_q = await db.execute(
            select(_LeaveRequest).where(
                _LeaveRequest.organizationId == organization_id,
                _LeaveRequest.memberId == target_member_id,
                _LeaveRequest.deletedAt.is_(None),
                _LeaveRequest.status == _LeaveRequestStatus.APPROVED,
                _LeaveRequest.startDate <= today,
                _LeaveRequest.endDate >= today,
            )
        )
        covering_leaves: list[_LeaveRequest] = leave_q.unique().scalars().all()

        for lr in covering_leaves:
            if lr.days <= 0:
                continue

            leave_type_id = lr.leaveTypeId
            lr.days = max(0.0, lr.days - 1.0)

            # Restore 1 day to leave balance
            balance_q = await db.execute(
                select(_LeaveBalance).where(
                    _LeaveBalance.organizationId == organization_id,
                    _LeaveBalance.memberId == target_member_id,
                    _LeaveBalance.leaveTypeId == leave_type_id,
                    _LeaveBalance.year == today.year,
                )
            )
            balance: _LeaveBalance | None = balance_q.scalar_one_or_none()
            if balance is not None and balance.used > 0:
                balance.used = max(0.0, balance.used - 1.0)
                balance.remaining = balance.allocated + balance.carriedForward - balance.used - balance.lapsed

    await _sync_weekly_plan_location_for_clock_in(
        db=db,
        organization_id=organization_id,
        user_id=target_member.userId,
        day=today,
        actual_location=validation_result.actual_location,
        commit=False,
    )

    await db.commit()
    await db.refresh(record)

    return record


# ---------------------------------------------------------------------------
# Clock-out
# ---------------------------------------------------------------------------


async def clock_out(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    policy: PolicyDefaults,
    clock_out_time: datetime | None = None,
    work_log_text: str | None = None,
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

    active = await get_active_session(db, organization_id, target_member_id)
    if active is None:
        raise HTTPException(
            status_code=400,
            detail="No active clock-in session found for this member",
        )

    now = (
        _normalize_attendance_datetime(clock_out_time)
        if clock_out_time is not None
        else datetime.now(tz=BUSINESS_TIMEZONE)
    )

    ci = _normalize_attendance_datetime(active.clockIn)

    if now <= ci:
        raise HTTPException(
            status_code=400,
            detail="clock_out must be after clock_in",
        )

    segments = _split_into_day_segments(ci, now)
    written: list[AttendanceRecord] = []
    active_project_id = active.projectId
    active_project_task_id = active.projectTaskId
    active_description = active.description.strip() if active.description else None
    normalized_work_log_text = (work_log_text or "").strip()

    if not active_description and not normalized_work_log_text:
        raise HTTPException(
            status_code=400,
            detail="Work summary is required before clock-out. Add it during clock-in or clock-out.",
        )

    for seg in segments:
        total = _compute_hours(seg.clock_in, seg.clock_out)
        overtime = _compute_overtime(total, policy.overtime_threshold)
        status = _derive_status(total, policy.half_day_max_hours)

        record = await _upsert_day_row(
            db=db,
            organization_id=organization_id,
            employee_id=target_member_id,
            day=seg.day,
            clock_in=seg.clock_in,
            clock_out=seg.clock_out,
            project_id=active_project_id,
            project_task_id=active_project_task_id,
            description=active_description,
            total_hours=total,
            overtime_hours=overtime,
            status=status,
            entered_by_manager_id=None,
            commit=False,
        )
        segment_description = active_description
        is_terminal_segment = seg.day == segments[-1].day
        if not segment_description and is_terminal_segment and normalized_work_log_text:
            segment_description = normalized_work_log_text
            record.description = normalized_work_log_text
            await db.flush()
        await _insert_clock_session_work_log_if_missing(
            db=db,
            record=record,
            segment=seg,
            project_id=active_project_id,
            project_task_id=active_project_task_id,
            description=segment_description,
        )
        if is_terminal_segment and normalized_work_log_text and not active_description:
            await _upsert_terminal_session_work_log_text(
                db=db,
                record=record,
                segment=seg,
                project_id=active_project_id,
                project_task_id=active_project_task_id,
                description=segment_description,
                work_log_text=normalized_work_log_text,
            )
        written.append(record)

    await db.commit()
    for record in written:
        await db.refresh(record)

    return written


# ---------------------------------------------------------------------------
# Manual day upsert
# ---------------------------------------------------------------------------


async def upsert_manual_day(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    policy: PolicyDefaults,
    day: date,
    clock_in_time: datetime | None,
    clock_out_time: datetime | None,
    entry_type: str | None = None,
    is_remote: bool | None = None,
) -> AttendanceRecord:
    """
    Manually create or replace a single attendance day row.

    - Validates scope.
    - Recomputes totals/status/overtime from provided clock times.
    - Sets enteredByManagerId to the actor.
    - Overwrites any existing row for that member/date.
    - If entry_type is provided (LEAVE/COMP_OFF/HOLIDAY/FLOATING_HOLIDAY), bypasses leave check and marks the cell.
    - If only is_remote is provided (no clock times, no entry_type), performs a minimal update
      of the isRemote flag on the existing record, or creates a new record with just isRemote set.
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    # ── Minimal is_remote update path (no clock times, no entry type) ──────
    if is_remote is not None and clock_in_time is None and clock_out_time is None and entry_type is None:
        result = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.organizationId == organization_id,
                AttendanceRecord.employeeId == target_member_id,
                AttendanceRecord.date == day,
            )
        )
        existing: AttendanceRecord | None = result.scalar_one_or_none()
        if existing is not None:
            existing.isRemote = is_remote
            await db.commit()
            await db.refresh(existing)
            return existing
        return await _upsert_day_row(
            db=db,
            organization_id=organization_id,
            employee_id=target_member_id,
            day=day,
            clock_in=None,
            clock_out=None,
            total_hours=None,
            overtime_hours=None,
            status="ABSENT",
            entered_by_manager_id=actor_member_id,
            is_remote=is_remote,
            entry_type=None,
        )

    if entry_type is None:
        if await _check_day_has_approved_leave(db, organization_id, target_member_id, day):
            raise HTTPException(
                status_code=400,
                detail="Cannot manually edit attendance for a day with approved leave.",
            )

    total_hours: float | None = None
    overtime_hours: float | None = None
    status = "ABSENT"

    if entry_type == "LEAVE":
        status = "ABSENT"
        total_hours = 0
    elif entry_type == "COMP_OFF":
        status = "PRESENT"
        total_hours = 0
    elif entry_type == "HOLIDAY":
        status = "ABSENT"
        total_hours = 0
    elif entry_type == "FLOATING_HOLIDAY":
        status = "ABSENT"
        total_hours = 0
    elif clock_in_time is not None and clock_out_time is not None:
        ci = _normalize_attendance_datetime(clock_in_time)
        co = _normalize_attendance_datetime(clock_out_time)

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

    return await _upsert_day_row(
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
        is_remote=is_remote or False,
        entry_type=entry_type,
    )


# ---------------------------------------------------------------------------
# Delete day entry
# ---------------------------------------------------------------------------


async def delete_day_entry(
    db: AsyncSession,
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

    if await _check_day_has_approved_leave(db, organization_id, target_member_id, day):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete attendance for a day with approved leave.",
        )

    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == target_member_id,
            AttendanceRecord.date == day,
        )
    )
    record: AttendanceRecord | None = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    await db.delete(record)
    await db.commit()


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


async def get_my_attendance(
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[tuple[AttendanceRecord, str | None]], int]:
    """
    Return paginated attendance rows for the calling member only.
    Never exposes other members' data.
    Returns tuples of (AttendanceRecord, employee_name).
    """
    from app.models.member import Member
    from app.models.user import User

    query = (
        select(AttendanceRecord, User.name, User.email)
        .join(Member, Member.id == AttendanceRecord.employeeId)
        .join(User, User.id == Member.userId)
        .where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == member_id,
        )
    )
    if date_from is not None:
        query = query.where(AttendanceRecord.date >= date_from)
    if date_to is not None:
        query = query.where(AttendanceRecord.date <= date_to)
    if status_filter is not None:
        query = query.where(AttendanceRecord.status == status_filter)

    total_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = total_result.scalar_one()
    rows_result = await db.execute(
        query.order_by(AttendanceRecord.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = rows_result.all()
    return [
        (record, _display_employee_name(name, email, record.employeeId))
        for record, name, email in rows
    ], total


async def list_attendance(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    scope: str,
    target_member_id: str | None = None,
    employee_name: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[tuple[AttendanceRecord, str | None]], int]:
    """
    Return paginated attendance rows respecting scope.

    - "self": always filters to actor's own records, ignores target_member_id / employee_name.
    - "organization": allows filtering by target_member_id or partial employee_name search.

    Returns tuples of (AttendanceRecord, employee_name).
    """
    from app.models.member import Member
    from app.models.user import User

    query = (
        select(AttendanceRecord, User.name, User.email)
        .join(Member, Member.id == AttendanceRecord.employeeId)
        .join(User, User.id == Member.userId)
        .where(
            AttendanceRecord.organizationId == organization_id,
        )
    )

    if scope == "self":
        query = query.where(AttendanceRecord.employeeId == actor_member_id)
    elif scope == "organization":
        if target_member_id is not None:
            query = query.where(AttendanceRecord.employeeId == target_member_id)
        elif employee_name is not None and employee_name.strip():
            query = query.where(User.name.ilike(f"%{employee_name.strip()}%"))
    # No team/department filtering — not supported in current schema.

    if date_from is not None:
        query = query.where(AttendanceRecord.date >= date_from)
    if date_to is not None:
        query = query.where(AttendanceRecord.date <= date_to)
    if status_filter is not None:
        query = query.where(AttendanceRecord.status == status_filter)

    total_result = await db.execute(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    total = total_result.scalar_one()
    rows_result = await db.execute(
        query.order_by(AttendanceRecord.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = rows_result.all()
    return [
        (record, _display_employee_name(name, email, record.employeeId))
        for record, name, email in rows
    ], total


async def get_attendance_day(
    db: AsyncSession,
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

    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == target_member_id,
            AttendanceRecord.date == day,
        )
    )
    record: AttendanceRecord | None = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return record


# ---------------------------------------------------------------------------
# Auto-stop helper (internal)
# ---------------------------------------------------------------------------


async def auto_stop_open_sessions(
    db: AsyncSession,
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
    now = datetime.now(tz=BUSINESS_TIMEZONE)
    cutoff = now - timedelta(hours=MAX_SESSION_HOURS)

    result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.clockIn.isnot(None),
            AttendanceRecord.clockOut.is_(None),
            AttendanceRecord.clockIn <= cutoff,
        )
    )
    open_sessions: list[AttendanceRecord] = result.scalars().all()

    written: list[AttendanceRecord] = []
    for session in open_sessions:
        ci = _normalize_attendance_datetime(session.clockIn)

        hard_stop = ci + timedelta(hours=MAX_SESSION_HOURS)
        segments = _split_into_day_segments(ci, hard_stop)

        for seg in segments:
            total = _compute_hours(seg.clock_in, seg.clock_out)
            overtime = _compute_overtime(total, policy.overtime_threshold)
            status = _derive_status(total, policy.half_day_max_hours)

            record = await _upsert_day_row(
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


# ---------------------------------------------------------------------------
# Bulk work-log helpers
# ---------------------------------------------------------------------------


@dataclass
class _NormalizedLog:
    """Internal representation of a validated, normalized work-log item."""

    start_time: datetime
    end_time: datetime
    project_id: str | None
    project_task_id: str | None
    title: str | None
    notes: str | None


@dataclass
class _DayDerivation:
    """Derived day-level values computed from a set of work logs."""

    clock_in: datetime
    clock_out: datetime
    total_hours: float
    overtime_hours: float
    status: str


def _normalize_datetime(dt_value: datetime) -> datetime:
    """Ensure a datetime is timezone-aware for attendance calculations."""
    return _normalize_attendance_datetime(dt_value)


def _validate_work_log_item(
    log_start: datetime,
    log_end: datetime,
    expected_date: date,
    index: int,
) -> _NormalizedLog:
    """
    Validate a single work-log item and return a normalized form.

    Raises HTTPException(422) for:
      - startTime >= endTime
      - either timestamp falls on a different calendar date than expected_date
    """
    start = _normalize_datetime(log_start)
    end = _normalize_datetime(log_end)

    if start >= end:
        raise HTTPException(
            status_code=422,
            detail=f"Log[{index}]: startTime must be before endTime",
        )

    # Validate both timestamps belong to the declared date.
    # We compare the date portion in UTC to keep things deterministic.
    if start.date() != expected_date:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Log[{index}]: startTime date {start.date()} "
                f"does not match declared date {expected_date}"
            ),
        )
    if end.date() != expected_date:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Log[{index}]: endTime date {end.date()} "
                f"does not match declared date {expected_date}"
            ),
        )

    return _NormalizedLog(
        start_time=start,
        end_time=end,
        project_id=None,
        project_task_id=None,
        title=None,
        notes=None,
    )


def _derive_day_from_logs(
    logs: list[_NormalizedLog],
    policy: PolicyDefaults,
) -> _DayDerivation:
    """
    Derive parent attendance record values from a list of work logs.

    Uses outer-span rule:
      clockIn  = earliest startTime across all logs
      clockOut = latest endTime across all logs
      totalHours = clockOut - clockIn (outer span, gaps ignored)
    """
    clock_in = min(log.start_time for log in logs)
    clock_out = max(log.end_time for log in logs)
    total_hours = _compute_hours(clock_in, clock_out)
    overtime_hours = _compute_overtime(total_hours, policy.overtime_threshold)
    status = _derive_status(total_hours, policy.half_day_max_hours)

    return _DayDerivation(
        clock_in=clock_in,
        clock_out=clock_out,
        total_hours=total_hours,
        overtime_hours=overtime_hours,
        status=status,
    )


async def _delete_work_logs_for_day(
    db: AsyncSession,
    organization_id: str,
    employee_id: str,
    day: date,
) -> None:
    """
    Delete all AttendanceWorkLog rows for a given employee/org/date.
    Called inside a transaction before inserting new logs.
    """
    from app.models.attendance_work_log import AttendanceWorkLog

    await db.execute(
        delete(AttendanceWorkLog).where(
            AttendanceWorkLog.organizationId == organization_id,
            AttendanceWorkLog.employeeId == employee_id,
            AttendanceWorkLog.date == day,
        )
    )


async def _insert_work_logs(
    db: AsyncSession,
    attendance_record_id: str,
    organization_id: str,
    employee_id: str,
    day: date,
    logs: list[_NormalizedLog],
) -> list[object]:
    """
    Bulk-insert AttendanceWorkLog rows for a single day.
    Returns the inserted ORM instances (refreshed).
    """
    from app.models.attendance_work_log import AttendanceWorkLog

    inserted: list[AttendanceWorkLog] = []
    for log in logs:
        row = AttendanceWorkLog(
            id=generate_uuid(),
            attendanceRecordId=attendance_record_id,
            organizationId=organization_id,
            employeeId=employee_id,
            date=day,
            startTime=log.start_time,
            endTime=log.end_time,
            projectId=log.project_id,
            projectTaskId=log.project_task_id,
            title=log.title,
            notes=log.notes,
        )
        db.add(row)
        inserted.append(row)

    await db.flush()  # assign DB state without committing the outer transaction
    for row in inserted:
        await db.refresh(row)

    return inserted


async def _insert_clock_session_work_log_if_missing(
    db: AsyncSession,
    record: AttendanceRecord,
    segment: DaySegment,
    project_id: str | None,
    project_task_id: str | None,
    description: str | None,
) -> None:
    """
    Materialize clock-in metadata into the timesheet work-log table.

    If the day already has work logs, leave them untouched to avoid overwriting
    manual edits or bulk-entered logs.
    """
    from app.models.attendance_work_log import AttendanceWorkLog

    if project_id is None or project_task_id is None:
        return

    existing_logs_result = await db.execute(
        select(AttendanceWorkLog.id).where(
            AttendanceWorkLog.attendanceRecordId == record.id,
        ).limit(1)
    )
    existing_log_id = existing_logs_result.scalar_one_or_none()
    if existing_log_id is not None:
        return

    db.add(
        AttendanceWorkLog(
            id=generate_uuid(),
            attendanceRecordId=record.id,
            organizationId=record.organizationId,
            employeeId=record.employeeId,
            date=record.date,
            startTime=segment.clock_in,
            endTime=segment.clock_out,
            projectId=project_id,
            projectTaskId=project_task_id,
            title=None,
            notes=description,
        )
    )
    await db.flush()


async def _upsert_terminal_session_work_log_text(
    db: AsyncSession,
    record: AttendanceRecord,
    segment: DaySegment,
    project_id: str | None,
    project_task_id: str | None,
    description: str | None,
    work_log_text: str,
) -> None:
    """
    Ensure the terminal day of a clock-out session has one session-level log row
    carrying the mandatory daily narrative.

    Rules:
      - No logs        -> create a session-level row.
      - One auto log   -> update it in place.
      - Many logs      -> update a matching session-level row if present,
                          otherwise create a separate session-level row.
    """
    matching_result = await db.execute(
        select(AttendanceWorkLog).where(
            AttendanceWorkLog.attendanceRecordId == record.id,
            AttendanceWorkLog.startTime == segment.clock_in,
            AttendanceWorkLog.endTime == segment.clock_out,
        )
    )
    matching_logs = list(matching_result.scalars().all())

    if matching_logs:
        target = matching_logs[0]
        target.projectId = project_id
        target.projectTaskId = project_task_id
        target.notes = work_log_text
        if target.title is None and description:
            target.title = description[:255]
        await db.flush()
        return

    all_logs_result = await db.execute(
        select(AttendanceWorkLog).where(
            AttendanceWorkLog.attendanceRecordId == record.id,
        )
    )
    all_logs = list(all_logs_result.scalars().all())

    if len(all_logs) == 1:
        target = all_logs[0]
        is_session_like = (
            target.startTime == segment.clock_in
            and target.endTime == segment.clock_out
        ) or target.title is None
        if is_session_like:
            target.projectId = project_id
            target.projectTaskId = project_task_id
            target.notes = work_log_text
            if target.title is None and description:
                target.title = description[:255]
            await db.flush()
            return

    db.add(
        AttendanceWorkLog(
            id=generate_uuid(),
            attendanceRecordId=record.id,
            organizationId=record.organizationId,
            employeeId=record.employeeId,
            date=record.date,
            startTime=segment.clock_in,
            endTime=segment.clock_out,
            projectId=project_id,
            projectTaskId=project_task_id,
            title=(description[:255] if description else None),
            notes=work_log_text,
        )
    )
    await db.flush()


# ---------------------------------------------------------------------------
# Bulk upsert
# ---------------------------------------------------------------------------


@dataclass
class BulkDayResult:
    """Internal result for one processed day."""

    record: AttendanceRecord
    logs: list[object]  # list[AttendanceWorkLog]


async def upsert_bulk_work_logs(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    policy: PolicyDefaults,
    days: list[object],  # list[BulkDayPayload] — imported at call site
) -> list[BulkDayResult]:
    """
    Save one or more days of bulk attendance work logs.

    For each submitted day:
      - If logs list is empty → delete that day's entry (parent + children).
      - Otherwise → validate logs, delete existing children, upsert parent,
        insert new children.

    All days are processed inside a single transaction.
    Raises HTTPException on any validation or scope failure.
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    results: list[BulkDayResult] = []

    try:
        for day_payload in days:
            day: date = day_payload.date
            raw_logs = day_payload.logs

            if await _check_day_has_approved_leave(db, organization_id, target_member_id, day):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot modify attendance for {day.isoformat()} — it has an approved leave.",
                )

            if not raw_logs:
                # Empty logs → treat as deletion of that day.
                await _delete_work_logs_for_day(db, organization_id, target_member_id, day)
                existing_record_result = await db.execute(
                    select(AttendanceRecord).where(
                        AttendanceRecord.organizationId == organization_id,
                        AttendanceRecord.employeeId == target_member_id,
                        AttendanceRecord.date == day,
                    )
                )
                existing_record: AttendanceRecord | None = existing_record_result.scalar_one_or_none()
                if existing_record is not None:
                    await db.delete(existing_record)
                # No result entry for deleted days — skip.
                continue

            # Validate and normalize each log item.
            normalized: list[_NormalizedLog] = []
            for idx, log_item in enumerate(raw_logs):
                validated_project_id, validated_project_task_id = (
                    await _validate_attendance_project_selection(
                        db=db,
                        organization_id=organization_id,
                        project_id=log_item.projectId,
                        project_task_id=log_item.projectTaskId,
                    )
                )
                n = _validate_work_log_item(
                    log_start=log_item.startTime,
                    log_end=log_item.endTime,
                    expected_date=day,
                    index=idx,
                )
                n.project_id = validated_project_id
                n.project_task_id = validated_project_task_id
                n.title = log_item.title
                n.notes = log_item.notes.strip() if log_item.notes else None
                normalized.append(n)

            # Sort logs by startTime ascending.
            normalized.sort(key=lambda x: x.start_time)

            # Derive parent record values from the outer span.
            derivation = _derive_day_from_logs(normalized, policy)

            # Delete existing child logs for this day.
            await _delete_work_logs_for_day(db, organization_id, target_member_id, day)

            # Upsert the parent attendance record.
            existing_parent_result = await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.organizationId == organization_id,
                    AttendanceRecord.employeeId == target_member_id,
                    AttendanceRecord.date == day,
                )
            )
            existing_parent: AttendanceRecord | None = existing_parent_result.scalar_one_or_none()

            if existing_parent is not None:
                existing_parent.clockIn = derivation.clock_in
                existing_parent.clockOut = derivation.clock_out
                existing_parent.totalHours = derivation.total_hours
                existing_parent.overtimeHours = derivation.overtime_hours
                existing_parent.status = derivation.status
                existing_parent.enteredByManagerId = None
                record = existing_parent
            else:
                record = AttendanceRecord(
                    id=generate_uuid(),
                    employeeId=target_member_id,
                    organizationId=organization_id,
                    date=day,
                    clockIn=derivation.clock_in,
                    clockOut=derivation.clock_out,
                    totalHours=derivation.total_hours,
                    overtimeHours=derivation.overtime_hours,
                    status=derivation.status,
                    enteredByManagerId=None,
                )
                db.add(record)

            await db.flush()
            await db.refresh(record)

            # Insert new child work logs.
            inserted_logs = await _insert_work_logs(
                db=db,
                attendance_record_id=record.id,
                organization_id=organization_id,
                employee_id=target_member_id,
                day=day,
                logs=normalized,
            )

            results.append(BulkDayResult(record=record, logs=inserted_logs))

        await db.commit()

    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save bulk attendance data",
        ) from exc

    return results


# ---------------------------------------------------------------------------
# Bulk range fetch
# ---------------------------------------------------------------------------


async def get_bulk_work_logs_range(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    date_from: date,
    date_to: date,
) -> list[BulkDayResult]:
    """
    Fetch attendance records and their child work logs for a date range.

    Returns results sorted by date ascending, logs sorted by startTime ascending.
    """
    from app.models.attendance_work_log import AttendanceWorkLog

    enforce_scope(actor_member_id, target_member_id, scope)

    records_result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == target_member_id,
            AttendanceRecord.date >= date_from,
            AttendanceRecord.date <= date_to,
        )
        .order_by(AttendanceRecord.date.asc())
    )
    records: list[AttendanceRecord] = records_result.scalars().all()

    if not records:
        return []

    record_ids = [r.id for r in records]

    all_logs_result = await db.execute(
        select(AttendanceWorkLog).where(AttendanceWorkLog.attendanceRecordId.in_(record_ids))
        .order_by(AttendanceWorkLog.startTime.asc())
    )
    all_logs: list[AttendanceWorkLog] = all_logs_result.scalars().all()

    # Group logs by attendanceRecordId for O(n) assembly.
    logs_by_record: dict[str, list[AttendanceWorkLog]] = {}
    for log in all_logs:
        logs_by_record.setdefault(log.attendanceRecordId, []).append(log)

    return [
        BulkDayResult(record=r, logs=logs_by_record.get(r.id, []))
        for r in records
    ]


# ---------------------------------------------------------------------------
# Bulk single-day fetch
# ---------------------------------------------------------------------------


async def get_bulk_work_logs_day(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    day: date,
) -> BulkDayResult | None:
    """
    Fetch one day's attendance record and its child work logs.

    Returns None if no entry exists for that day.
    """
    from app.models.attendance_work_log import AttendanceWorkLog

    enforce_scope(actor_member_id, target_member_id, scope)

    record_result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == target_member_id,
            AttendanceRecord.date == day,
        )
    )
    record: AttendanceRecord | None = record_result.scalar_one_or_none()

    if record is None:
        return None

    logs_result = await db.execute(
        select(AttendanceWorkLog).where(AttendanceWorkLog.attendanceRecordId == record.id)
        .order_by(AttendanceWorkLog.startTime.asc())
    )
    logs: list[AttendanceWorkLog] = logs_result.scalars().all()

    return BulkDayResult(record=record, logs=logs)


# ---------------------------------------------------------------------------
# Bulk day deletion
# ---------------------------------------------------------------------------


async def delete_bulk_work_logs_day(
    db: AsyncSession,
    organization_id: str,
    actor_member_id: str,
    target_member_id: str,
    scope: str,
    day: date,
) -> None:
    """
    Delete one day's bulk attendance entry (parent record + all child logs).

    Child logs are deleted first via the cascade or explicit delete.
    Raises 404 if no entry exists for that day.
    """
    enforce_scope(actor_member_id, target_member_id, scope)

    record_result = await db.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.employeeId == target_member_id,
            AttendanceRecord.date == day,
        )
    )
    record: AttendanceRecord | None = record_result.scalar_one_or_none()

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="No attendance entry found for this date",
        )

    # Delete child logs explicitly before the parent to be safe,
    # even though the FK has ondelete="CASCADE".
    await _delete_work_logs_for_day(db, organization_id, target_member_id, day)

    await db.delete(record)
    await db.commit()


def _work_log_preview(value: str | None, limit: int = 120) -> str | None:
    if value is None:
        return None
    trimmed = " ".join(value.split())
    if len(trimmed) <= limit:
        return trimmed
    return f"{trimmed[: limit - 1].rstrip()}…"


def _build_work_log_report_selects(
    organization_id: str,
):
    notes_subquery = (
        select(AttendanceWorkLog.notes)
        .where(
            AttendanceWorkLog.attendanceRecordId == AttendanceRecord.id,
            AttendanceWorkLog.organizationId == organization_id,
            AttendanceWorkLog.notes.is_not(None),
            AttendanceWorkLog.notes != "",
        )
        .order_by(AttendanceWorkLog.startTime.desc(), AttendanceWorkLog.createdAt.desc())
        .limit(1)
        .scalar_subquery()
    )
    department_name_subquery = (
        select(func.min(Department.name))
        .select_from(DepartmentMember)
        .join(Department, Department.id == DepartmentMember.departmentId)
        .where(
            DepartmentMember.memberId == AttendanceRecord.employeeId,
            Department.organizationId == organization_id,
        )
        .scalar_subquery()
    )
    return notes_subquery, department_name_subquery


def _apply_work_log_report_filters(
    query,
    organization_id: str,
    *,
    date_from: date | None,
    date_to: date | None,
    department_id: str | None,
    employee_id: str | None,
    employee_name: str | None,
):
    query = query.where(AttendanceRecord.organizationId == organization_id)
    if date_from is not None:
        query = query.where(AttendanceRecord.date >= date_from)
    if date_to is not None:
        query = query.where(AttendanceRecord.date <= date_to)
    if employee_id is not None:
        query = query.where(AttendanceRecord.employeeId == employee_id)
    if employee_name:
        term = f"%{employee_name.strip()}%"
        query = query.where(User.name.ilike(term))
    if department_id is not None:
        query = query.where(
            AttendanceRecord.employeeId.in_(
                select(DepartmentMember.memberId).where(
                    DepartmentMember.departmentId == department_id,
                )
            )
        )
    return query


async def list_work_log_reports(
    db: AsyncSession,
    organization_id: str,
    *,
    date_from: date | None,
    date_to: date | None,
    department_id: str | None,
    employee_id: str | None,
    employee_name: str | None,
    page: int,
    page_size: int,
) -> tuple[list[WorkLogReportRowData], int, WorkLogReportSummaryData]:
    notes_subquery, department_name_subquery = _build_work_log_report_selects(
        organization_id
    )

    base_query = (
        select(
            AttendanceRecord.id,
            AttendanceRecord.employeeId,
            User.name,
            User.email,
            AttendanceRecord.date,
            AttendanceRecord.clockIn,
            AttendanceRecord.clockOut,
            AttendanceRecord.totalHours,
            department_name_subquery.label("departmentName"),
            Project.name.label("projectName"),
            ProjectTask.name.label("taskName"),
            notes_subquery.label("dailyWorkLog"),
        )
        .join(Member, Member.id == AttendanceRecord.employeeId)
        .join(User, User.id == Member.userId)
        .outerjoin(Project, Project.id == AttendanceRecord.projectId)
        .outerjoin(ProjectTask, ProjectTask.id == AttendanceRecord.projectTaskId)
    )
    base_query = _apply_work_log_report_filters(
        base_query,
        organization_id,
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
        employee_id=employee_id,
        employee_name=employee_name,
    )

    count_query = (
        select(
            func.count(distinct(AttendanceRecord.id)),
            func.coalesce(func.sum(AttendanceRecord.totalHours), 0.0),
            func.count(distinct(AttendanceRecord.employeeId)),
        )
        .select_from(AttendanceRecord)
        .join(Member, Member.id == AttendanceRecord.employeeId)
        .join(User, User.id == Member.userId)
    )
    count_query = _apply_work_log_report_filters(
        count_query,
        organization_id,
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
        employee_id=employee_id,
        employee_name=employee_name,
    )
    total, total_hours, employee_count = (await db.execute(count_query)).one()

    paged_query = (
        base_query.order_by(AttendanceRecord.date.desc(), User.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(paged_query)

    rows = [
        WorkLogReportRowData(
            attendance_record_id=row.id,
            employee_id=row.employeeId,
            employee_name=_display_employee_name(row.name, row.email, row.employeeId),
            employee_email=row.email,
            day=row.date,
            clock_in=row.clockIn,
            clock_out=row.clockOut,
            total_hours=row.totalHours,
            department_name=row.departmentName,
            project_name=row.projectName,
            task_name=row.taskName,
            daily_work_log=row.dailyWorkLog,
        )
        for row in result
    ]

    return (
        rows,
        int(total or 0),
        WorkLogReportSummaryData(
            total_days=int(total or 0),
            total_hours=round(float(total_hours or 0.0), 4),
            employee_count=int(employee_count or 0),
        ),
    )


async def get_work_log_report_detail(
    db: AsyncSession,
    organization_id: str,
    attendance_record_id: str,
) -> WorkLogReportRowData | None:
    notes_subquery, department_name_subquery = _build_work_log_report_selects(
        organization_id
    )
    query = (
        select(
            AttendanceRecord.id,
            AttendanceRecord.employeeId,
            User.name,
            User.email,
            AttendanceRecord.date,
            AttendanceRecord.clockIn,
            AttendanceRecord.clockOut,
            AttendanceRecord.totalHours,
            department_name_subquery.label("departmentName"),
            Project.name.label("projectName"),
            ProjectTask.name.label("taskName"),
            notes_subquery.label("dailyWorkLog"),
        )
        .join(Member, Member.id == AttendanceRecord.employeeId)
        .join(User, User.id == Member.userId)
        .outerjoin(Project, Project.id == AttendanceRecord.projectId)
        .outerjoin(ProjectTask, ProjectTask.id == AttendanceRecord.projectTaskId)
        .where(
            AttendanceRecord.organizationId == organization_id,
            AttendanceRecord.id == attendance_record_id,
        )
    )
    row = (await db.execute(query)).one_or_none()
    if row is None:
        return None
    return WorkLogReportRowData(
        attendance_record_id=row.id,
        employee_id=row.employeeId,
        employee_name=_display_employee_name(row.name, row.email, row.employeeId),
        employee_email=row.email,
        day=row.date,
        clock_in=row.clockIn,
        clock_out=row.clockOut,
        total_hours=row.totalHours,
        department_name=row.departmentName,
        project_name=row.projectName,
        task_name=row.taskName,
        daily_work_log=row.dailyWorkLog,
    )


async def export_work_log_reports(
    db: AsyncSession,
    organization_id: str,
    *,
    date_from: date | None,
    date_to: date | None,
    department_id: str | None,
    employee_id: str | None,
    employee_name: str | None,
) -> list[WorkLogReportRowData]:
    notes_subquery, department_name_subquery = _build_work_log_report_selects(
        organization_id
    )
    query = (
        select(
            AttendanceRecord.id,
            AttendanceRecord.employeeId,
            User.name,
            User.email,
            AttendanceRecord.date,
            AttendanceRecord.clockIn,
            AttendanceRecord.clockOut,
            AttendanceRecord.totalHours,
            department_name_subquery.label("departmentName"),
            Project.name.label("projectName"),
            ProjectTask.name.label("taskName"),
            notes_subquery.label("dailyWorkLog"),
        )
        .join(Member, Member.id == AttendanceRecord.employeeId)
        .join(User, User.id == Member.userId)
        .outerjoin(Project, Project.id == AttendanceRecord.projectId)
        .outerjoin(ProjectTask, ProjectTask.id == AttendanceRecord.projectTaskId)
    )
    query = _apply_work_log_report_filters(
        query,
        organization_id,
        date_from=date_from,
        date_to=date_to,
        department_id=department_id,
        employee_id=employee_id,
        employee_name=employee_name,
    ).order_by(AttendanceRecord.date.desc(), User.name.asc())

    result = await db.execute(query)
    return [
        WorkLogReportRowData(
            attendance_record_id=row.id,
            employee_id=row.employeeId,
            employee_name=_display_employee_name(row.name, row.email, row.employeeId),
            employee_email=row.email,
            day=row.date,
            clock_in=row.clockIn,
            clock_out=row.clockOut,
            total_hours=row.totalHours,
            department_name=row.departmentName,
            project_name=row.projectName,
            task_name=row.taskName,
            daily_work_log=row.dailyWorkLog,
        )
        for row in result
    ]
