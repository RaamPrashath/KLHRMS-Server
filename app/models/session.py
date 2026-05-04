from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.models.base import Base, TimestampMixin, generate_uuid


class Session(Base, TimestampMixin):
    __tablename__ = "session"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    expiresAt: Mapped[datetime] = mapped_column(nullable=False)

    token: Mapped[str] = mapped_column(String(255), nullable=False)

    ipAddress: Mapped[str | None] = mapped_column(String(45), nullable=True)
    userAgent: Mapped[str | None] = mapped_column(String(512), nullable=True)

    userId: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        UniqueConstraint("token", name="session_token_key"),
        Index("session_userId_idx", "userId"),
    )