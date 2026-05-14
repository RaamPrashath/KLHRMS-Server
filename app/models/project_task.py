from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class ProjectTask(Base):
    __tablename__ = "project_task"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    projectId: Mapped[str] = mapped_column(String(36), ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="tasks")

    __table_args__ = (
        Index("project_task_projectId_idx", "projectId"),
    )
