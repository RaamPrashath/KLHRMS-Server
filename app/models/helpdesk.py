"""Helpdesk ticket — internal IT/HR support tickets."""
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class HelpdeskTicket(HRMSBase):
    __tablename__ = "helpdesk_tickets"

    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[str] = mapped_column(String(100), nullable=False)
    # it | hr | payroll | facilities | other

    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    # low | medium | high | critical

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    # open | in_progress | resolved | closed

    raised_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )
