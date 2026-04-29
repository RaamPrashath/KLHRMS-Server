"""Employee — core HRMS entity."""
import uuid

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class Employee(HRMSBase):
    __tablename__ = "employees"

    # Better Auth user reference
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    employee_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True, index=True
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )

    designation: Mapped[str | None] = mapped_column(String(150), nullable=True)
    employment_type: Mapped[str] = mapped_column(String(50), nullable=False, default="full_time")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")

    date_of_joining: Mapped[str | None] = mapped_column(Date, nullable=True)
    date_of_birth: Mapped[str | None] = mapped_column(Date, nullable=True)
