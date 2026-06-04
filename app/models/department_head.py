from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class DepartmentHead(Base):
    __tablename__ = "departmentHead"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    departmentId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("department.id", ondelete="CASCADE"),
        nullable=False,
    )
    memberId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("member.id", ondelete="CASCADE"),
        nullable=False,
    )

    assignedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    department = relationship("Department", back_populates="heads")
    member = relationship("Member", back_populates="departmentHeads")

    __table_args__ = (
        UniqueConstraint("departmentId", "memberId", name="departmentHead_departmentId_memberId_key"),
        Index("departmentHead_departmentId_idx", "departmentId"),
        Index("departmentHead_memberId_idx", "memberId"),
    )
