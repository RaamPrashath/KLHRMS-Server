"""Leave management data access layer with SQLAlchemy queries."""
from datetime import date

from sqlalchemy import and_, func, select

from app.models.leave import (
    EmployeeReporting,
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveTypeConfig,
)
from app.shared.lib.base_repository import BaseRepository
from app.shared.utils.enums import LeaveStatus


class LeaveTypeConfigRepository(BaseRepository[LeaveTypeConfig]):
    model = LeaveTypeConfig

    async def get_by_name(self, name: str) -> LeaveTypeConfig | None:
        """Get leave type by name (case-insensitive)"""
        result = await self.session.execute(
            self._base_query()
            .where(func.lower(LeaveTypeConfig.name) == func.lower(name))
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[LeaveTypeConfig]:
        """List all active leave types ordered by name"""
        result = await self.session.execute(
            self._base_query()
            .where(LeaveTypeConfig.is_active.is_(True))
            .order_by(LeaveTypeConfig.name)
        )
        return list(result.scalars().all())


class LeaveRequestRepository(BaseRepository[LeaveRequest]):
    model = LeaveRequest

    async def get_by_id_with_type(self, request_id) -> LeaveRequest | None:
        """Get leave request with leave type eager loaded"""
        result = await self.session.execute(
            self._base_query()
            .where(LeaveRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def list_requests(
        self,
        employee_id: str | None = None,
        status: LeaveStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[LeaveRequest]:
        """List leave requests with optional filters"""
        query = self._base_query()

        if employee_id:
            query = query.where(LeaveRequest.employee_id == employee_id)

        if status:
            query = query.where(LeaveRequest.status == str(status))

        query = query.order_by(LeaveRequest.created_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_team_requests(
        self,
        manager_id: str,
        status: LeaveStatus | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[LeaveRequest]:
        """List leave requests for employees reporting to a manager"""
        # Get all employees reporting to this manager
        reporting_result = await self.session.execute(
            select(EmployeeReporting.employee_id).where(
                EmployeeReporting.organization_id == self.organization_id,
                EmployeeReporting.manager_id == manager_id,
                EmployeeReporting.deleted_at.is_(None),
            )
        )
        direct_reports = [r for r in reporting_result.scalars().all()]

        if not direct_reports:
            return []

        query = self._base_query().where(LeaveRequest.employee_id.in_(direct_reports))

        if status:
            query = query.where(LeaveRequest.status == str(status))

        query = query.order_by(LeaveRequest.created_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_calendar_events(
        self,
        date_from: date,
        date_to: date,
        employee_id: str | None = None,
    ) -> list[LeaveRequest]:
        """Get approved leave requests within date range for calendar"""
        query = self._base_query().where(
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.start_date <= date_to,
            LeaveRequest.end_date >= date_from,
        )

        if employee_id:
            query = query.where(LeaveRequest.employee_id == employee_id)

        query = query.order_by(LeaveRequest.start_date)

        result = await self.session.execute(query)
        return list(result.scalars().all())


class LeaveBalanceRepository(BaseRepository[LeaveBalance]):
    model = LeaveBalance

    async def get_balance(
        self, employee_id: str, leave_type_id: str, year: int
    ) -> LeaveBalance | None:
        """Get specific leave balance for employee, type and year"""
        result = await self.session.execute(
            self._base_query()
            .where(LeaveBalance.employee_id == employee_id)
            .where(LeaveBalance.leave_type_id == leave_type_id)
            .where(LeaveBalance.year == year)
        )
        return result.scalar_one_or_none()

    async def list_balances(
        self,
        employee_id: str | None = None,
        year: int | None = None,
    ) -> list[LeaveBalance]:
        """List leave balances with optional filters"""
        query = self._base_query()

        if employee_id:
            query = query.where(LeaveBalance.employee_id == employee_id)

        if year:
            query = query.where(LeaveBalance.year == year)

        query = query.order_by(LeaveBalance.year.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())


class HolidayRepository(BaseRepository[Holiday]):
    model = Holiday

    async def list_holidays(
        self,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Holiday]:
        """List holidays within optional date range"""
        query = self._base_query().order_by(Holiday.holiday_date)

        if date_from:
            query = query.where(Holiday.holiday_date >= date_from)

        if date_to:
            query = query.where(Holiday.holiday_date <= date_to)

        result = await self.session.execute(query)
        return list(result.scalars().all())


class EmployeeReportingRepository(BaseRepository[EmployeeReporting]):
    model = EmployeeReporting

    async def get_by_employee(self, employee_id: str) -> EmployeeReporting | None:
        """Get reporting relationship by employee ID"""
        result = await self.session.execute(
            self._base_query().where(EmployeeReporting.employee_id == employee_id)
        )
        return result.scalar_one_or_none()

    async def get_manager_id(self, employee_id: str) -> str | None:
        """Get manager ID for an employee"""
        record = await self.get_by_employee(employee_id)
        return record.manager_id if record else None

    async def list_direct_reports(self, manager_id: str) -> list[str]:
        """List all employee IDs reporting to a manager"""
        result = await self.session.execute(
            select(EmployeeReporting.employee_id).where(
                EmployeeReporting.organization_id == self.organization_id,
                EmployeeReporting.manager_id == manager_id,
                EmployeeReporting.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def set_manager(self, employee_id: str, manager_id: str) -> EmployeeReporting:
        """Set or update employee's manager"""
        existing = await self.get_by_employee(employee_id)

        if existing:
            existing.manager_id = manager_id
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        return await self.create(employee_id=employee_id, manager_id=manager_id)
