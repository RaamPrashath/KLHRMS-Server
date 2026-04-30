from sqlalchemy import DateTime, ForeignKey, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "account"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    accountId: Mapped[str] = mapped_column(String(255), nullable=False)
    providerId: Mapped[str] = mapped_column(String(100), nullable=False)

    userId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )

    accessToken: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    refreshToken: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    idToken: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    accessTokenExpiresAt: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refreshTokenExpiresAt: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("account_userId_idx", "userId"),
    )