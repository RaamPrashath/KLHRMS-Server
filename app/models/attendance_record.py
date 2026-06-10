from sqlalchemy import Date, DateTime, Float, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date
from app.models.base import Base, generate_uuid


class AttendanceRecord(Base):
    __tablename__ = "attendanceRecord"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    employeeId: Mapped[str] = mapped_column(String(36), nullable=False)
    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)

    date: Mapped[date] = mapped_column(Date, nullable=False)

    clockIn: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clockOut: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projectId: Mapped[str | None] = mapped_column(String(36), nullable=True)
    projectTaskId: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    totalHours: Mapped[float | None] = mapped_column(Float, nullable=True)
    overtimeHours: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="ABSENT")

    isRemote: Mapped[bool] = mapped_column(nullable=False, default=False)

    enteredByManagerId: Mapped[str | None] = mapped_column(String(36), nullable=True)

    entryType: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    workLog = relationship("AttendanceWorkLog", back_populates="attendanceRecord")

    __table_args__ = (
        UniqueConstraint("employeeId", "date", name="attendanceRecord_employeeId_date_key"),
        Index("attendanceRecord_organizationId_idx", "organizationId"),
        Index("attendanceRecord_organizationId_date_idx", "organizationId", "date"),
        Index("attendanceRecord_organizationId_employeeId_idx", "organizationId", "employeeId"),
        Index("attendanceRecord_projectId_idx", "projectId"),
        Index("attendanceRecord_projectTaskId_idx", "projectTaskId"),
    )
