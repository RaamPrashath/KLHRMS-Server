from sqlalchemy import DateTime, String, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Verification(Base, TimestampMixin):
    __tablename__ = "verification"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)

    expiresAt: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("verification_identifier_idx", "identifier"),
    )