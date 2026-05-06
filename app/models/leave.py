"""Leave management models."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid
from app.shared.utils.enums import LeaveRequestStatus


class LeaveType(Base):
    __tablename__ = "leave_type"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quota: Mapped[float] = mapped_column(Float, nullable=False)
    carryForward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    isPaid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    balances: Mapped[list["LeaveBalance"]] = relationship("LeaveBalance", back_populates="leave_type")
    requests: Mapped[list["LeaveRequest"]] = relationship("LeaveRequest", back_populates="leave_type")

    __table_args__ = (
        UniqueConstraint("organizationId", "name", name="leave_type_organizationId_name_key"),
        Index("leave_type_organizationId_idx", "organizationId"),
        Index("leave_type_organizationId_deletedAt_idx", "organizationId", "deletedAt"),
    )


class LeaveRequest(Base):
    __tablename__ = "leave_request"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    memberId: Mapped[str] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    leaveTypeId: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_type.id", ondelete="RESTRICT"), nullable=False
    )

    startDate: Mapped[date] = mapped_column(Date, nullable=False)
    endDate: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=LeaveRequestStatus.PENDING)

    approvedById: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    approverComment: Mapped[str | None] = mapped_column(Text, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False)
    cancelledAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    member = relationship("Member", foreign_keys=[memberId], back_populates="leave_requests")
    approved_by = relationship("Member", foreign_keys=[approvedById], back_populates="approved_leave_requests")
    leave_type = relationship("LeaveType", back_populates="requests")

    __table_args__ = (
        Index("leave_request_organizationId_idx", "organizationId"),
        Index("leave_request_organizationId_memberId_idx", "organizationId", "memberId"),
        Index("leave_request_organizationId_status_idx", "organizationId", "status"),
        Index("leave_request_organizationId_leaveTypeId_idx", "organizationId", "leaveTypeId"),
        Index("leave_request_organizationId_startDate_idx", "organizationId", "startDate"),
        Index("leave_request_organizationId_startDate_endDate_idx", "organizationId", "startDate", "endDate"),
        Index("leave_request_approvedById_idx", "approvedById"),
    )


class LeaveBalance(Base):
    __tablename__ = "leave_balance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    memberId: Mapped[str] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False
    )
    leaveTypeId: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_type.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    allocated: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    used: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    remaining: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    carriedForward: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    lapsed: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False)

    member = relationship("Member", foreign_keys=[memberId], back_populates="leave_balances")
    leave_type = relationship("LeaveType", back_populates="balances")

    __table_args__ = (
        UniqueConstraint("organizationId", "memberId", "leaveTypeId", "year", name="leave_balance_org_member_type_year_key"),
        Index("leave_balance_organizationId_idx", "organizationId"),
        Index("leave_balance_organizationId_memberId_year_idx", "organizationId", "memberId", "year"),
        Index("leave_balance_organizationId_leaveTypeId_year_idx", "organizationId", "leaveTypeId", "year"),
    )


class Holiday(Base):
    __tablename__ = "holiday"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    holidayDate: Mapped[date] = mapped_column(Date, nullable=False)
    isRecurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()", onupdate="now()", nullable=False)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("holiday_organizationId_idx", "organizationId"),
        Index("holiday_organizationId_holidayDate_idx", "organizationId", "holidayDate"),
        Index("holiday_organizationId_deletedAt_idx", "organizationId", "deletedAt"),
    )