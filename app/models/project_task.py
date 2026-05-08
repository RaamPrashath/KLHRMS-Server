from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class ProjectTask(Base):
    __tablename__ = "project_task"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    projectId: Mapped[str] = mapped_column(String(36), ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignedMemberId: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="TODO")
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project = relationship("Project", back_populates="tasks")
    assigned_member = relationship("Member")

    __table_args__ = (
        Index("project_task_projectId_idx", "projectId"),
        Index("project_task_assignedMemberId_idx", "assignedMemberId"),
        Index("project_task_projectId_status_idx", "projectId", "status"),
    )
