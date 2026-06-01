from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class MicrosoftSyncLog(HRMSBase):
    __tablename__ = "microsoft_sync_log"

    sync_run_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("microsoft_sync_run.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
