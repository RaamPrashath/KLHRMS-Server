from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import Base, generate_uuid


class DepartmentMember(Base):
    __tablename__ = "departmentMember"

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

    joinedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    department = relationship("Department", back_populates="members")
    member = relationship("Member", back_populates="departmentMembers")

    __table_args__ = (
        UniqueConstraint("departmentId", "memberId", name="departmentMember_departmentId_memberId_key"),
        Index("departmentMember_departmentId_idx", "departmentId"),
        Index("departmentMember_memberId_idx", "memberId"),
    )