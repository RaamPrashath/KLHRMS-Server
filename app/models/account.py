from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, generate_uuid


class Account(Base, TimestampMixin):
    __tablename__ = "account"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    accountId: Mapped[str] = mapped_column(String(255), nullable=False)
    providerId: Mapped[str] = mapped_column(String(100), nullable=False)

    userId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    accessToken: Mapped[str | None] = mapped_column(String(2048))
    refreshToken: Mapped[str | None] = mapped_column(String(2048))
    idToken: Mapped[str | None] = mapped_column(String(2048))

    accessTokenExpiresAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    refreshTokenExpiresAt: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    scope: Mapped[str | None] = mapped_column(String(255))
    password: Mapped[str | None] = mapped_column(String(255))

    user = relationship("User", back_populates="accounts")

    __table_args__ = (
        Index("account_userId_idx", "userId"),
    )
