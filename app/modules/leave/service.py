"""Leave management business logic."""
import uuid
from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from app.models.auth_tables import PrismaUser  # adjust if your User model name differs
from app.models.leave import (
    EmployeeReporting,
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveTypeConfig,
)
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
from app.shared.auth_context import AuthContext
from app.shared.constants import ROLE_ADMIN, ROLE_HR, ROLE_MANAGER, ROLE_SUPER_ADMIN
from app.shared.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from app.shared.utils.enums import LeaveStatus


class LeaveService:
    def __init__(
        self,
        type_repo: LeaveTypeConfigRepository,
        request_repo: LeaveRequestRepository,
        balance_repo: LeaveBalanceRepository,
        holiday_repo: HolidayRepository,
        reporting_repo: EmployeeReportingRepository,
        auth: AuthContext,
    ) -> None:
        self.type_repo = type_repo
        self.request_repo = request_repo
        self.balance_repo = balance_repo
        self.holiday_repo = holiday_repo
        self.reporting_repo = reporting_repo
        self.auth = auth

    # ── Leave Type Management ─────────────────────────────────────────────────

    async def list_types(self) -> list[LeaveTypeConfigRead]:
        types = await self.type_repo.list_active()
        return [LeaveTypeConfigRead.model_validate(t) for t in types]

    async def list_all_types(self) -> list[LeaveTypeConfigRead]:
        types = await self.type_repo.list()
        return [LeaveTypeConfigRead.model_validate(t) for t in types]

    async def create_type(self, data: LeaveTypeConfigCreate) -> LeaveTypeConfigRead:
        existing = await self.type_repo.get_by_name(data.name)
        if existing:
            raise ConflictError(f"Leave type '{data.name}' already exists")

        kwargs: dict = dict(
            name=data.name,
            quota=data.quota,
            carry_forward=data.carry_forward,
            is_paid=data.is_paid,
            color=data.color,
        )
        if data.description is not None:
            kwargs["description"] = data.description

        leave_type = await self.type_repo.create(**kwargs)
        return LeaveTypeConfigRead.model_validate(leave_type)

    async def update_type(
        self, type_id: uuid.UUID, data: LeaveTypeConfigUpdate
    ) -> LeaveTypeConfigRead:
        leave_type = await self.type_repo.get_by_id(type_id)
        if not leave_type:
            raise NotFoundError("Leave type not found")

        if data.name is not None:
            existing = await self.type_repo.get_by_name(data.name)
            if existing and existing.id != type_id:
                raise ConflictError(f"Leave type '{data.name}' already exists")
            leave_type.name = data.name

        if data.quota is not None:
            leave_type.quota = data.quota
        if data.carry_forward is not None:
            leave_type.carry_forward = data.carry_forward
        if data.is_paid is not None:
            leave_type.is_paid = data.is_paid
        if data.color is not None:
            leave_type.color = data.color
        if data.is_active is not None:
            leave_type.is_active = data.is_active
        if data.description is not None:
            leave_type.description = data.description

        await self.type_repo.session.flush()
        await self.type_repo.session.refresh(leave_type)
        return LeaveTypeConfigRead.model_validate(leave_type)

    async def delete_type(self, type_id: uuid.UUID) -> bool:
        leave_type = await self.type_repo.get_by_id(type_id)
        if not leave_type:
            raise NotFoundError("Leave type not found")
        return await self.type_repo.soft_delete(type_id)

    # ── Leave Request Submission ──────────────────────────────────────────────

    async def submit_request(self, data: LeaveRequestCreate) -> LeaveRequestRead:
        if data.end_date < data.start_date:
            raise BusinessRuleError("End date must be on or after start date")

        leave_type = await self.type_repo.get_by_id(data.leave_type_id)
        if not leave_type:
            raise NotFoundError("Leave type not found")
        if not leave_type.is_active:
            raise BusinessRuleError("This leave type is not active")

        days = self._calculate_working_days(data.start_date, data.end_date)
        if days <= 0:
            raise BusinessRuleError("Invalid date range — no working days selected")

        if leave_type.is_paid:
            balance = await self.balance_repo.get_balance(
                self.auth.user_id,
                str(data.leave_type_id),
                data.start_date.year,
            )
            if balance and balance.remaining < days:
                raise BusinessRuleError(
                    f"Insufficient leave balance. Available: {balance.remaining}, Requested: {days}"
                )

        leave_request = await self.request_repo.create(
            employee_id=self.auth.user_id,
            leave_type_id=str(data.leave_type_id),
            start_date=data.start_date,
            end_date=data.end_date,
            days=days,
            reason=data.reason,
            status=LeaveStatus.PENDING,
        )

        return self._build_request_read(leave_request, leave_type=leave_type)

    async def cancel_request(self, request_id: uuid.UUID) -> LeaveRequestRead:
        leave_request = await self.request_repo.get_by_id(request_id)
        if not leave_request:
            raise NotFoundError("Leave request not found")

        if leave_request.employee_id != self.auth.user_id:
            raise PermissionDeniedError("You can only cancel your own leave requests")

        if leave_request.status != LeaveStatus.PENDING:
            raise BusinessRuleError("Only pending leave requests can be cancelled")

        leave_request.status = LeaveStatus.CANCELLED
        await self.request_repo.session.flush()

        results = await self._fetch_requests_enriched(
            employee_id=leave_request.employee_id,
            request_id=leave_request.id,
        )
        return results[0] if results else self._build_request_read(leave_request)

    # ── Approval Workflow ─────────────────────────────────────────────────────

    async def approve_request(
        self, request_id: uuid.UUID, data: LeaveRequestApprove
    ) -> LeaveRequestRead:
        leave_request = await self.request_repo.get_by_id(request_id)
        if not leave_request:
            raise NotFoundError("Leave request not found")

        if leave_request.status != LeaveStatus.PENDING:
            raise BusinessRuleError("Only pending leave requests can be approved")

        await self._check_approval_permission(leave_request.employee_id)

        leave_type = await self.type_repo.get_by_id(
            uuid.UUID(str(leave_request.leave_type_id))
        )
        if leave_type and leave_type.is_paid:
            balance = await self.balance_repo.get_balance(
                leave_request.employee_id,
                str(leave_request.leave_type_id),
                leave_request.start_date.year,
            )
            if not balance:
                raise BusinessRuleError("No leave balance found for this employee")
            if balance.remaining < leave_request.days:
                raise BusinessRuleError("Insufficient leave balance for approval")

            balance.used += leave_request.days
            balance.remaining = balance.allocated - balance.used

        leave_request.status = LeaveStatus.APPROVED
        leave_request.approved_by_id = self.auth.user_id
        leave_request.approver_comment = data.comment

        await self.request_repo.session.flush()

        results = await self._fetch_requests_enriched(request_id=leave_request.id)
        return results[0] if results else self._build_request_read(leave_request)

    async def reject_request(
        self, request_id: uuid.UUID, data: LeaveRequestReject
    ) -> LeaveRequestRead:
        leave_request = await self.request_repo.get_by_id(request_id)
        if not leave_request:
            raise NotFoundError("Leave request not found")

        if leave_request.status != LeaveStatus.PENDING:
            raise BusinessRuleError("Only pending leave requests can be rejected")

        await self._check_approval_permission(leave_request.employee_id)

        leave_request.status = LeaveStatus.REJECTED
        leave_request.approved_by_id = self.auth.user_id
        leave_request.approver_comment = data.comment

        await self.request_repo.session.flush()

        results = await self._fetch_requests_enriched(request_id=leave_request.id)
        return results[0] if results else self._build_request_read(leave_request)

    async def list_requests(
        self,
        status: LeaveStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[LeaveRequestRead]:
        if self._can_view_all_org():
            return await self._fetch_requests_enriched(
                status=status, offset=offset, limit=limit
            )
        elif self.auth.role == ROLE_MANAGER:
            return await self._fetch_requests_enriched(
                manager_id=self.auth.user_id,
                status=status,
                offset=offset,
                limit=limit,
            )
        else:
            return await self._fetch_requests_enriched(
                employee_id=self.auth.user_id,
                status=status,
                offset=offset,
                limit=limit,
            )

    # ── Leave Balance ─────────────────────────────────────────────────────────

    async def get_balances(
        self,
        employee_id: str | None = None,
        year: int | None = None,
    ) -> list[LeaveBalanceRead]:
        target_employee = employee_id or self.auth.user_id

        if employee_id and employee_id != self.auth.user_id:
            if not self._can_view_all_org():
                if self.auth.role == ROLE_MANAGER:
                    direct_reports = await self.reporting_repo.list_direct_reports(
                        self.auth.user_id
                    )
                    if employee_id not in direct_reports:
                        raise PermissionDeniedError(
                            "You can only view balances of your direct reports"
                        )
                else:
                    raise PermissionDeniedError("You can only view your own balances")

        return await self._fetch_balances_enriched(
            employee_id=target_employee, year=year
        )

    async def allocate_balance(self, data: LeaveBalanceAllocate) -> LeaveBalanceRead:
        if not self._can_manage_balances():
            raise PermissionDeniedError(
                "You do not have permission to allocate leave balances"
            )

        leave_type = await self.type_repo.get_by_id(data.leave_type_id)
        if not leave_type:
            raise NotFoundError("Leave type not found")

        existing = await self.balance_repo.get_balance(
            data.employee_id, str(data.leave_type_id), data.year
        )

        if existing:
            existing.allocated = data.allocated
            existing.remaining = data.allocated - existing.used
            await self.balance_repo.session.flush()
            await self.balance_repo.session.refresh(existing)
        else:
            existing = await self.balance_repo.create(
                employee_id=data.employee_id,
                leave_type_id=str(data.leave_type_id),
                year=data.year,
                allocated=data.allocated,
                used=0,
                remaining=data.allocated,
            )

        results = await self._fetch_balances_enriched(
            employee_id=data.employee_id, year=data.year
        )
        for r in results:
            if r.id == existing.id:
                return r
        return self._build_balance_read(existing)

    async def auto_allocate_balances(self, data: LeaveBalanceAutoAllocate) -> int:
        if not self._can_manage_balances():
            raise PermissionDeniedError(
                "You do not have permission to allocate leave balances"
            )

        active_types = await self.type_repo.list_active()
        employees = await self._get_all_employees()
        allocated_count = 0

        for leave_type in active_types:
            if leave_type.quota <= 0:
                continue

            for employee_id in employees:
                existing = await self.balance_repo.get_balance(
                    employee_id, str(leave_type.id), data.year
                )
                if existing:
                    continue

                await self.balance_repo.create(
                    employee_id=employee_id,
                    leave_type_id=str(leave_type.id),
                    year=data.year,
                    allocated=leave_type.quota,
                    used=0,
                    remaining=leave_type.quota,
                )
                allocated_count += 1

        return allocated_count

    # ── Calendar ──────────────────────────────────────────────────────────────

    async def get_calendar_events(
        self,
        date_from: date,
        date_to: date,
        employee_id: str | None = None,
    ) -> list[CalendarEvent]:
        if self._can_view_all_org():
            results = await self._fetch_requests_enriched(
                status=LeaveStatus.APPROVED,
                date_from=date_from,
                date_to=date_to,
                limit=1000,
            )
        elif self.auth.role == ROLE_MANAGER:
            results = await self._fetch_requests_enriched(
                manager_id=self.auth.user_id,
                status=LeaveStatus.APPROVED,
                date_from=date_from,
                date_to=date_to,
                limit=1000,
            )
        else:
            results = await self._fetch_requests_enriched(
                employee_id=self.auth.user_id,
                status=LeaveStatus.APPROVED,
                date_from=date_from,
                date_to=date_to,
                limit=1000,
            )

        if employee_id:
            results = [r for r in results if r.employee_id == employee_id]

        return [
            CalendarEvent(
                id=r.id,
                employee_id=r.employee_id,
                employee_name=r.employee_name,
                leave_type_id=r.leave_type_id,
                leave_type_name=r.leave_type_name,
                leave_type_color=r.leave_type_color,
                start_date=r.start_date,
                end_date=r.end_date,
                days=r.days,
                status=r.status,
            )
            for r in results
        ]

    # ── Holiday Management ────────────────────────────────────────────────────

    async def list_holidays(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[HolidayRead]:
        holidays = await self.holiday_repo.list_holidays(date_from, date_to)
        return [HolidayRead.model_validate(h) for h in holidays]

    async def create_holiday(self, data: HolidayCreate) -> HolidayRead:
        holiday = await self.holiday_repo.create(
            name=data.name,
            holiday_date=data.holiday_date,
            is_recurring=data.is_recurring,
            description=data.description,
        )
        return HolidayRead.model_validate(holiday)

    async def update_holiday(
        self, holiday_id: uuid.UUID, data: HolidayUpdate
    ) -> HolidayRead:
        holiday = await self.holiday_repo.get_by_id(holiday_id)
        if not holiday:
            raise NotFoundError("Holiday not found")

        if data.name is not None:
            holiday.name = data.name
        if data.holiday_date is not None:
            holiday.holiday_date = data.holiday_date
        if data.is_recurring is not None:
            holiday.is_recurring = data.is_recurring
        if data.description is not None:
            holiday.description = data.description

        await self.holiday_repo.session.flush()
        await self.holiday_repo.session.refresh(holiday)
        return HolidayRead.model_validate(holiday)

    async def delete_holiday(self, holiday_id: uuid.UUID) -> bool:
        holiday = await self.holiday_repo.get_by_id(holiday_id)
        if not holiday:
            raise NotFoundError("Holiday not found")
        return await self.holiday_repo.soft_delete(holiday_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _calculate_working_days(self, start: date, end: date) -> float:
        days = 0
        current = start
        while current <= end:
            if current.weekday() < 5:
                days += 1
            current += timedelta(days=1)
        return float(days)

    async def _check_approval_permission(self, employee_id: str) -> None:
        if self.auth.role in (ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN):
            return
        if self.auth.role == ROLE_MANAGER:
            direct_reports = await self.reporting_repo.list_direct_reports(
                self.auth.user_id
            )
            if employee_id not in direct_reports:
                raise PermissionDeniedError(
                    "You can only approve/reject leave requests from your direct reports"
                )
            return
        raise PermissionDeniedError(
            "You do not have permission to approve/reject leave requests"
        )

    def _can_view_all_org(self) -> bool:
        return self.auth.role in (ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN)

    def _can_manage_balances(self) -> bool:
        return self.auth.role in (ROLE_SUPER_ADMIN, ROLE_HR, ROLE_ADMIN)

    async def _get_all_employees(self) -> list[str]:
        """Return all user IDs that are members of this organization."""
        from app.models.auth_tables import PrismaMember

        result = await self.balance_repo.session.execute(
            select(PrismaMember.user_id)
            .where(PrismaMember.organization_id == str(self.auth.organization_id))
            .distinct()
        )
        return list(result.scalars().all())

    # ── Enriched ORM queries ──────────────────────────────────────────────────

    async def _fetch_requests_enriched(
        self,
        employee_id: str | None = None,
        manager_id: str | None = None,
        request_id: uuid.UUID | None = None,
        status: LeaveStatus | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[LeaveRequestRead]:
        """
        Fetch leave requests joined with user names and leave type info
        using SQLAlchemy ORM — no raw SQL.

        Uses aliased() to join the user table twice:
        once for the employee, once for the approver.
        """
        Employee = aliased(PrismaUser, name="employee")
        Approver = aliased(PrismaUser, name="approver")

        stmt = (
            select(
                LeaveRequest,
                Employee.name.label("employee_name"),
                Employee.email.label("employee_email"),
                Approver.name.label("approver_name"),
                LeaveTypeConfig.name.label("leave_type_name"),
                LeaveTypeConfig.color.label("leave_type_color"),
            )
            .outerjoin(Employee, Employee.id == LeaveRequest.employee_id)
            .outerjoin(Approver, Approver.id == LeaveRequest.approved_by_id)
            .outerjoin(
                LeaveTypeConfig,
                and_(
                    # leave_type_id is stored as text, LeaveTypeConfig.id is UUID —
                    # cast the text column to UUID so SQLAlchemy handles the type match
                    func.cast(LeaveRequest.leave_type_id, LeaveTypeConfig.id.type)
                    == LeaveTypeConfig.id,
                    LeaveTypeConfig.organization_id == LeaveRequest.organization_id,
                    LeaveTypeConfig.deleted_at.is_(None),
                ),
            )
            .where(
                LeaveRequest.organization_id == self.auth.organization_id,
                LeaveRequest.deleted_at.is_(None),
            )
        )

        if request_id is not None:
            stmt = stmt.where(LeaveRequest.id == request_id)

        if employee_id is not None:
            stmt = stmt.where(LeaveRequest.employee_id == employee_id)

        if manager_id is not None:
            # Subquery: employee IDs that report to this manager in this org
            subq = select(EmployeeReporting.employee_id).where(
                EmployeeReporting.manager_id == manager_id,
                EmployeeReporting.organization_id == self.auth.organization_id,
                EmployeeReporting.deleted_at.is_(None),
            )
            stmt = stmt.where(LeaveRequest.employee_id.in_(subq))

        if status is not None:
            stmt = stmt.where(LeaveRequest.status == str(status))

        if date_from is not None:
            stmt = stmt.where(LeaveRequest.end_date >= date_from)

        if date_to is not None:
            stmt = stmt.where(LeaveRequest.start_date <= date_to)

        stmt = stmt.order_by(LeaveRequest.created_at.desc()).offset(offset).limit(limit)

        result = await self.request_repo.session.execute(stmt)
        rows = result.all()

        return [
            LeaveRequestRead(
                id=lr.id,
                organization_id=lr.organization_id,
                employee_id=lr.employee_id,
                employee_name=employee_name,
                employee_email=employee_email,
                leave_type_id=str(lr.leave_type_id),
                leave_type_name=leave_type_name,
                leave_type_color=leave_type_color,
                start_date=lr.start_date,
                end_date=lr.end_date,
                days=lr.days,
                reason=lr.reason,
                status=lr.status,
                approved_by_id=lr.approved_by_id,
                approver_name=approver_name,
                approver_comment=lr.approver_comment,
                created_at=lr.created_at.date() if lr.created_at else None,
            )
            for lr, employee_name, employee_email, approver_name, leave_type_name, leave_type_color
            in rows
        ]

    async def _fetch_balances_enriched(
        self,
        employee_id: str | None = None,
        year: int | None = None,
    ) -> list[LeaveBalanceRead]:
        """
        Fetch leave balances joined with leave type name/color and user name
        using SQLAlchemy ORM — no raw SQL.
        """
        stmt = (
            select(
                LeaveBalance,
                PrismaUser.name.label("employee_name"),
                LeaveTypeConfig.name.label("leave_type_name"),
                LeaveTypeConfig.color.label("leave_type_color"),
            )
            .outerjoin(PrismaUser, PrismaUser.id == LeaveBalance.employee_id)
            .outerjoin(
                LeaveTypeConfig,
                and_(
                    func.cast(LeaveBalance.leave_type_id, LeaveTypeConfig.id.type)
                    == LeaveTypeConfig.id,
                    LeaveTypeConfig.organization_id == LeaveBalance.organization_id,
                    LeaveTypeConfig.deleted_at.is_(None),
                ),
            )
            .where(
                LeaveBalance.organization_id == self.auth.organization_id,
                LeaveBalance.deleted_at.is_(None),
            )
        )

        if employee_id is not None:
            stmt = stmt.where(LeaveBalance.employee_id == employee_id)

        if year is not None:
            stmt = stmt.where(LeaveBalance.year == year)

        stmt = stmt.order_by(LeaveBalance.year.desc(), LeaveTypeConfig.name)

        result = await self.balance_repo.session.execute(stmt)
        rows = result.all()

        return [
            LeaveBalanceRead(
                id=lb.id,
                organization_id=lb.organization_id,
                employee_id=lb.employee_id,
                employee_name=employee_name,
                leave_type_id=str(lb.leave_type_id),
                leave_type_name=leave_type_name,
                leave_type_color=leave_type_color,
                year=lb.year,
                allocated=lb.allocated,
                used=lb.used,
                remaining=lb.remaining,
                carried_forward=lb.carried_forward,
                lapsed=lb.lapsed,
            )
            for lb, employee_name, leave_type_name, leave_type_color in rows
        ]

    # ── Fallback builders (used right after create, before DB round-trip) ─────

    def _build_request_read(
        self,
        leave_request: LeaveRequest,
        leave_type: LeaveTypeConfig | None = None,
    ) -> LeaveRequestRead:
        return LeaveRequestRead(
            id=leave_request.id,
            organization_id=leave_request.organization_id,
            employee_id=leave_request.employee_id,
            leave_type_id=str(leave_request.leave_type_id),
            leave_type_name=leave_type.name if leave_type else None,
            leave_type_color=leave_type.color if leave_type else None,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
            days=leave_request.days,
            reason=leave_request.reason,
            status=leave_request.status,
            approved_by_id=leave_request.approved_by_id,
            approver_comment=leave_request.approver_comment,
            created_at=leave_request.created_at.date() if leave_request.created_at else None,
        )

    def _build_balance_read(self, balance: LeaveBalance) -> LeaveBalanceRead:
        return LeaveBalanceRead(
            id=balance.id,
            organization_id=balance.organization_id,
            employee_id=balance.employee_id,
            leave_type_id=str(balance.leave_type_id),
            year=balance.year,
            allocated=balance.allocated,
            used=balance.used,
            remaining=balance.remaining,
            carried_forward=getattr(balance, "carried_forward", 0),
            lapsed=getattr(balance, "lapsed", 0),
        )