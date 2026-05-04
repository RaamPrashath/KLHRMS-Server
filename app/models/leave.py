"""Leave management models."""
from datetime import date

from sqlalchemy import Boolean, Date, Float, Integer, String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.lib.base_model import HRMSBase
from app.shared.utils.enums import LeaveStatus


class LeaveTypeConfig(HRMSBase):
    """Configurable leave types per organization (Annual, Sick, Casual, etc.)"""
    __tablename__ = "leave_type_configs"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    quota: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carry_forward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False, default="#3b82f6")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    balances: Mapped[list["LeaveBalance"]] = relationship("LeaveBalance", back_populates="leave_type")
    requests: Mapped[list["LeaveRequest"]] = relationship("LeaveRequest", back_populates="leave_type")


class LeaveRequest(HRMSBase):
    """Employee leave requests with approval workflow"""
    __tablename__ = "leave_requests"

    employee_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    leave_type_id: Mapped[str] = mapped_column(ForeignKey("leave_type_configs.id"), nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LeaveStatus] = mapped_column(String(20), nullable=False, default=LeaveStatus.PENDING)
    approved_by_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approver_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    leave_type: Mapped["LeaveTypeConfig"] = relationship("LeaveTypeConfig", back_populates="requests")


class LeaveBalance(HRMSBase):
    """Per-employee leave balance tracking per type and year"""
    __tablename__ = "leave_balances"

    employee_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    leave_type_id: Mapped[str] = mapped_column(ForeignKey("leave_type_configs.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    used: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    remaining: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carried_forward: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    lapsed: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # Relationships
    leave_type: Mapped["LeaveTypeConfig"] = relationship("LeaveTypeConfig", back_populates="balances")

    __table_args__ = (
        # Unique constraint: one balance per employee per type per year per organization
        UniqueConstraint(
            "organization_id", "employee_id", "leave_type_id", "year",
            name="uq_leave_balance_org_emp_type_year",
        ),
    )


class Holiday(HRMSBase):
    """Public holidays per organization"""
    __tablename__ = "holidays"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmployeeReporting(HRMSBase):
    """Employee to manager reporting relationship"""
    __tablename__ = "employee_reporting"

    employee_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True, unique=True)
    manager_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
