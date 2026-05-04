"""Leave management endpoints."""
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.models.auth_tables import PrismaMember, PrismaUser
from app.modules.leave.repository import (
    EmployeeReportingRepository,
    HolidayRepository,
    LeaveBalanceRepository,
    LeaveRequestRepository,
    LeaveTypeConfigRepository,
)
from app.modules.leave.schema import (
    CalendarEvent,
    HolidayCreate,
    HolidayRead,
    HolidayUpdate,
    LeaveBalanceAllocate,
    LeaveBalanceAutoAllocate,
    LeaveBalanceRead,
    LeaveRequestApprove,
    LeaveRequestCreate,
    LeaveRequestRead,
    LeaveRequestReject,
    LeaveTypeConfigCreate,
    LeaveTypeConfigRead,
    LeaveTypeConfigUpdate,
)
from app.modules.leave.service import LeaveService
from app.shared.constants import ROLE_ADMIN, ROLE_HR, ROLE_MANAGER, ROLE_SUPER_ADMIN
from app.shared.deps.auth import AuthContextDep, DbSession, require_roles


class OrgMemberRead(BaseModel):
    """Lightweight member record for employee pickers."""
    user_id: str
    name: str | None
    email: str

router = APIRouter(prefix="/leaves", tags=["leaves"])


def get_service(db: DbSession, auth: AuthContextDep) -> LeaveService:
    type_repo = LeaveTypeConfigRepository(session=db, organization_id=auth.organization_id)
    request_repo = LeaveRequestRepository(session=db, organization_id=auth.organization_id)
    balance_repo = LeaveBalanceRepository(session=db, organization_id=auth.organization_id)
    holiday_repo = HolidayRepository(session=db, organization_id=auth.organization_id)
    reporting_repo = EmployeeReportingRepository(session=db, organization_id=auth.organization_id)
    return LeaveService(
        type_repo=type_repo,
        request_repo=request_repo,
        balance_repo=balance_repo,
        holiday_repo=holiday_repo,
        reporting_repo=reporting_repo,
        auth=auth,
    )


ServiceDep = Annotated[LeaveService, Depends(get_service)]


# ── Leave Types ───────────────────────────────────────────────────────────────


@router.get(
    "/types",
    response_model=list[LeaveTypeConfigRead],
    status_code=status.HTTP_200_OK,
    summary="List active leave types",
)
async def list_leave_types(service: ServiceDep) -> list[LeaveTypeConfigRead]:
    """Get all active leave types for the organization"""
    return await service.list_types()


@router.get(
    "/types/all",
    response_model=list[LeaveTypeConfigRead],
    status_code=status.HTTP_200_OK,
    summary="List all leave types (including inactive)",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def list_all_leave_types(service: ServiceDep) -> list[LeaveTypeConfigRead]:
    """Get all leave types including inactive (HR/Admin only)"""
    return await service.list_all_types()


@router.post(
    "/types",
    response_model=LeaveTypeConfigRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create leave type",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def create_leave_type(
    data: LeaveTypeConfigCreate,
    service: ServiceDep,
) -> LeaveTypeConfigRead:
    """Create a new leave type (HR/Admin only)"""
    return await service.create_type(data)


@router.put(
    "/types/{type_id}",
    response_model=LeaveTypeConfigRead,
    status_code=status.HTTP_200_OK,
    summary="Update leave type",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def update_leave_type(
    type_id: uuid.UUID,
    data: LeaveTypeConfigUpdate,
    service: ServiceDep,
) -> LeaveTypeConfigRead:
    """Update an existing leave type (HR/Admin only)"""
    return await service.update_type(type_id, data)


@router.delete(
    "/types/{type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete leave type",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def delete_leave_type(
    type_id: uuid.UUID,
    service: ServiceDep,
) -> None:
    """Soft delete a leave type (HR/Admin only)"""
    await service.delete_type(type_id)


# ── Leave Requests ────────────────────────────────────────────────────────────


@router.get(
    "/requests",
    response_model=list[LeaveRequestRead],
    status_code=status.HTTP_200_OK,
    summary="List leave requests",
)
async def list_leave_requests(
    service: ServiceDep,
    status_filter: str | None = Query(default=None, alias="status"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
) -> list[LeaveRequestRead]:
    """List leave requests based on user role:
    - Employees: their own requests
    - Managers: their team's requests
    - HR/Admin: all requests
    """
    from app.shared.utils.enums import LeaveStatus

    leave_status = LeaveStatus(status_filter) if status_filter else None
    return await service.list_requests(status=leave_status, offset=offset, limit=limit)


@router.post(
    "/requests",
    response_model=LeaveRequestRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit leave request",
)
async def submit_leave_request(
    data: LeaveRequestCreate,
    service: ServiceDep,
) -> LeaveRequestRead:
    """Submit a new leave request"""
    return await service.submit_request(data)


@router.post(
    "/requests/{request_id}/cancel",
    response_model=LeaveRequestRead,
    status_code=status.HTTP_200_OK,
    summary="Cancel leave request",
)
async def cancel_leave_request(
    request_id: uuid.UUID,
    service: ServiceDep,
) -> LeaveRequestRead:
    """Cancel a pending leave request (employee only)"""
    return await service.cancel_request(request_id)


@router.post(
    "/requests/{request_id}/approve",
    response_model=LeaveRequestRead,
    status_code=status.HTTP_200_OK,
    summary="Approve leave request",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN, ROLE_MANAGER))],
)
async def approve_leave_request(
    request_id: uuid.UUID,
    service: ServiceDep,
    data: LeaveRequestApprove = Body(default_factory=LeaveRequestApprove),
) -> LeaveRequestRead:
    """
    Approve a pending leave request (Manager/HR/Admin only).

    Body is optional — sending {} or omitting the body entirely both work.
    An optional comment is stored as the approver's note.
    """
    return await service.approve_request(request_id, data)


@router.post(
    "/requests/{request_id}/reject",
    response_model=LeaveRequestRead,
    status_code=status.HTTP_200_OK,
    summary="Reject leave request",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN, ROLE_MANAGER))],
)
async def reject_leave_request(
    request_id: uuid.UUID,
    service: ServiceDep,
    data: LeaveRequestReject = Body(...),
) -> LeaveRequestRead:
    """
    Reject a pending leave request (Manager/HR/Admin only).

    Body is required and must include a non-empty comment so the employee
    understands why their request was rejected.
    """
    return await service.reject_request(request_id, data)


# ── Leave Balances ────────────────────────────────────────────────────────────


@router.get(
    "/balances",
    response_model=list[LeaveBalanceRead],
    status_code=status.HTTP_200_OK,
    summary="Get leave balances",
)
async def get_leave_balances(
    service: ServiceDep,
    employee_id: str | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> list[LeaveBalanceRead]:
    """Get leave balances for an employee"""
    return await service.get_balances(employee_id=employee_id, year=year)


@router.post(
    "/balances/allocate",
    response_model=LeaveBalanceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Manually allocate leave balance",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def allocate_leave_balance(
    data: LeaveBalanceAllocate,
    service: ServiceDep,
) -> LeaveBalanceRead:
    """Manually allocate leave balance to an employee (HR/Admin only)"""
    return await service.allocate_balance(data)


@router.post(
    "/balances/auto-allocate",
    status_code=status.HTTP_200_OK,
    summary="Auto-allocate balances for all employees",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def auto_allocate_balances(
    data: LeaveBalanceAutoAllocate,
    service: ServiceDep,
) -> dict:
    """Auto-allocate leave balances based on type quotas (HR/Admin only)"""
    count = await service.auto_allocate_balances(data)
    return {"message": f"Allocated balances for {count} records", "count": count}


# ── Calendar ──────────────────────────────────────────────────────────────────


@router.get(
    "/calendar",
    response_model=list[CalendarEvent],
    status_code=status.HTTP_200_OK,
    summary="Get calendar events",
)
async def get_calendar_events(
    service: ServiceDep,
    date_from: date = Query(...),
    date_to: date = Query(...),
    employee_id: str | None = Query(default=None),
) -> list[CalendarEvent]:
    """Get approved leave events for calendar view"""
    return await service.get_calendar_events(
        date_from=date_from, date_to=date_to, employee_id=employee_id
    )


# ── Org Members (for employee picker in balance management) ──────────────────


@router.get(
    "/members",
    response_model=list[OrgMemberRead],
    status_code=status.HTTP_200_OK,
    summary="List org members for employee picker",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def list_org_members(
    auth: AuthContextDep,
    db: DbSession,
) -> list[OrgMemberRead]:
    """
    Return all members of the current organization with their user details.
    Used by HR/Admin to populate the employee picker in balance management.
    """
    stmt = (
        select(PrismaMember, PrismaUser)
        .join(PrismaUser, PrismaUser.id == PrismaMember.user_id)
        .where(PrismaMember.organization_id == str(auth.organization_id))
        .order_by(PrismaUser.name)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        OrgMemberRead(
            user_id=member.user_id,
            name=user.name,
            email=user.email,
        )
        for member, user in rows
    ]


# ── Holidays ──────────────────────────────────────────────────────────────────


@router.get(
    "/holidays",
    response_model=list[HolidayRead],
    status_code=status.HTTP_200_OK,
    summary="List holidays",
)
async def list_holidays(
    service: ServiceDep,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
) -> list[HolidayRead]:
    """List public holidays for the organization"""
    return await service.list_holidays(date_from=date_from, date_to=date_to)


@router.post(
    "/holidays",
    response_model=HolidayRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create holiday",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def create_holiday(
    data: HolidayCreate,
    service: ServiceDep,
) -> HolidayRead:
    """Create a new holiday (HR/Admin only)"""
    return await service.create_holiday(data)


@router.put(
    "/holidays/{holiday_id}",
    response_model=HolidayRead,
    status_code=status.HTTP_200_OK,
    summary="Update holiday",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def update_holiday(
    holiday_id: uuid.UUID,
    data: HolidayUpdate,
    service: ServiceDep,
) -> HolidayRead:
    """Update an existing holiday (HR/Admin only)"""
    return await service.update_holiday(holiday_id, data)


@router.delete(
    "/holidays/{holiday_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete holiday",
    dependencies=[Depends(require_roles(ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN))],
)
async def delete_holiday(
    holiday_id: uuid.UUID,
    service: ServiceDep,
) -> None:
    """Soft delete a holiday (HR/Admin only)"""
    await service.delete_holiday(holiday_id)
