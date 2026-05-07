from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class Project(Base):
    __tablename__ = "project"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    teamId: Mapped[str | None] = mapped_column(String(36), ForeignKey("team.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    clientName: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    budgetedHours: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    startDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    endDate: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="ACTIVE")
    billable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    deletedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    team = relationship("Team", back_populates="projects")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("ProjectTask", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        Index("project_organizationId_idx", "organizationId"),
        Index("project_teamId_idx", "teamId"),
        Index("project_organizationId_status_idx", "organizationId", "status"),
        Index("project_organizationId_deletedAt_idx", "organizationId", "deletedAt"),
    )
