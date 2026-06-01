from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import HRMSBase


class EmployeeGroup(HRMSBase):
    __tablename__ = "employee_group"

    microsoft_group_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    memberships = relationship("EmployeeGroupMembership", back_populates="group", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_employee_group_org_ms_id", "organization_id", "microsoft_group_id", unique=True),
    )
