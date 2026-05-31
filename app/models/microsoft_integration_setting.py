from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class MicrosoftIntegrationSetting(HRMSBase):
    __tablename__ = "microsoft_integration_setting"

    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    client_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    client_secret: Mapped[str] = mapped_column("client_secret_ciphertext", Text, nullable=False, default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_microsoft_integration_setting_org", "organization_id"),
    )
