from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class Team(Base):
    __tablename__ = "team"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    departmentId: Mapped[str] = mapped_column(String(36), ForeignKey("department.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    leadMemberId: Mapped[str | None] = mapped_column(String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="ACTIVE")
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    department = relationship("Department")
    lead_member = relationship("Member", foreign_keys=[leadMemberId])
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("organizationId", "departmentId", "name", name="team_organizationId_departmentId_name_key"),
        Index("team_organizationId_idx", "organizationId"),
        Index("team_departmentId_idx", "departmentId"),
        Index("team_organizationId_status_idx", "organizationId", "status"),
        Index("team_leadMemberId_idx", "leadMemberId"),
    )
