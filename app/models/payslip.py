"""Payslip — individual employee payslip within a payroll run."""
import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class Payslip(HRMSBase):
    __tablename__ = "payslips"

    payroll_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payrolls.id"), nullable=False, index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True
    )

    gross_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    total_deductions: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    net_salary: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    # Earnings and deductions breakdown stored as JSON
    earnings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    deductions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="generated")
    # generated | sent | acknowledged

    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
