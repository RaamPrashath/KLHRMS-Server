"""Daily attendance record per employee."""
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class Attendance(HRMSBase):
    __tablename__ = "attendance"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="present")
    # present | absent | half_day | on_leave | holiday | weekend
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    # manual | biometric | mobile
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
