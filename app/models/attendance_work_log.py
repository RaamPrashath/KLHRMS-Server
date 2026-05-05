from sqlalchemy import Date, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from app.models.base import Base, generate_uuid


class AttendanceWorkLog(Base):
    __tablename__ = "attendanceWorkLog"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    attendanceRecordId: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("attendanceRecord.id", ondelete="CASCADE"),
        nullable=False,
    )

    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)
    employeeId: Mapped[str] = mapped_column(String(36), nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)

    startTime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    endTime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    attendanceRecord = relationship("AttendanceRecord", back_populates="workLog")

    __table_args__ = (
        Index("attendanceWorkLog_attendanceRecordId_idx", "attendanceRecordId"),
        Index("attendanceWorkLog_organizationId_idx", "organizationId"),
        Index("attendanceWorkLog_organizationId_employeeId_idx", "organizationId", "employeeId"),
        Index("attendanceWorkLog_organizationId_date_idx", "organizationId", "date"),
    )