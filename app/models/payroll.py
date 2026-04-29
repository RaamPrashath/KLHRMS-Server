"""Payroll run — monthly payroll processing record."""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class Payroll(HRMSBase):
    __tablename__ = "payrolls"

    period_month: Mapped[int] = mapped_column(nullable=False)   # 1–12
    period_year: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    # draft | processing | completed | cancelled

    processed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )
    processed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    total_gross: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_deductions: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_net: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
