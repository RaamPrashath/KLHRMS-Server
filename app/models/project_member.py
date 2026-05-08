from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class ProjectMember(Base):
    __tablename__ = "project_member"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    projectId: Mapped[str] = mapped_column(String(36), ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    memberId: Mapped[str] = mapped_column(String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    allocatedHours: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="members")
    member = relationship("Member")

    __table_args__ = (
        UniqueConstraint("projectId", "memberId", name="project_member_projectId_memberId_key"),
        Index("project_member_projectId_idx", "projectId"),
        Index("project_member_memberId_idx", "memberId"),
    )
