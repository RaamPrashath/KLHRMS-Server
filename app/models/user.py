from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class User(Base, TimestampMixin):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    emailVerified: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)

    image: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # relationships
    sessions = relationship("Session", back_populates="user")
    accounts = relationship("Account", back_populates="user")
    members = relationship("Member", back_populates="user")

    __table_args__ = (
        UniqueConstraint("email", name="user_email_key"),
    )