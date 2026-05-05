from sqlalchemy import DateTime, String, Index
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.models.base import Base, TimestampMixin, generate_uuid


class Verification(Base, TimestampMixin):
    __tablename__ = "verification"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)

    expiresAt: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("verification_identifier_idx", "identifier"),
    )