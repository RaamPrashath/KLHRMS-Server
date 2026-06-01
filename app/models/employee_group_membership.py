from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import HRMSBase


class EmployeeGroupMembership(HRMSBase):
    __tablename__ = "employee_group_membership"

    group_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_group.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee.id", ondelete="CASCADE"), nullable=False
    )

    group = relationship("EmployeeGroup", back_populates="memberships")
    employee = relationship("Employee")

    __table_args__ = (
        UniqueConstraint("group_id", "employee_id", name="uq_group_membership"),
    )
