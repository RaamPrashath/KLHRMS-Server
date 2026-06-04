from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class TeamMember(Base):
    __tablename__ = "team_member"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    teamId: Mapped[str] = mapped_column(String(36), ForeignKey("team.id", ondelete="CASCADE"), nullable=False)
    memberId: Mapped[str] = mapped_column(String(36), ForeignKey("member.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    joinedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    team = relationship("Team", back_populates="members")
    member = relationship("Member")

    __table_args__ = (
        UniqueConstraint("teamId", "memberId", name="team_member_teamId_memberId_key"),
        Index("team_member_teamId_idx", "teamId"),
        Index("team_member_memberId_idx", "memberId"),
    )
