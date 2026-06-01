from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class MicrosoftSyncRun(HRMSBase):
    __tablename__ = "microsoft_sync_run"

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_progress")
    total_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("member.id", ondelete="SET NULL"), nullable=True
    )
