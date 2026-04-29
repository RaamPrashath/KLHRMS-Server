"""Asset — company assets assigned to employees."""
import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class Asset(HRMSBase):
    __tablename__ = "assets"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_tag: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    # laptop | phone | vehicle | furniture | software_license …

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="available")
    # available | assigned | under_repair | retired

    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True, index=True
    )
    assigned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
