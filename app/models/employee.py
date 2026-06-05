from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import HRMSBase


class Employee(HRMSBase):
    __tablename__ = "employee"

    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    microsoft_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_principal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mobile_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    office_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_phones: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    given_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    surname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    street_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employee_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    employee_hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    usage_location: Mapped[str | None] = mapped_column(String(10), nullable=True)
    user_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_date_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    account_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    profile_photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    manager_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="SET NULL"), nullable=True
    )
    manager_chain: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    manager = relationship("Employee", remote_side="Employee.id", back_populates="direct_reports")
    direct_reports = relationship("Employee", back_populates="manager")

    __table_args__ = (
        Index("ix_employee_org_microsoft_id", "organization_id", "microsoft_id", unique=True),
        Index("ix_employee_org_email", "organization_id", "email"),
        Index("ix_employee_status", "organization_id", "status"),
    )
