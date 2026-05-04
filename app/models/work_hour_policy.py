from sqlalchemy import Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, generate_uuid


class WorkHourPolicy(Base):
    __tablename__ = "workHourPolicy"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )

    organizationId: Mapped[str] = mapped_column(String(36), nullable=False)

    standardHoursPerDay: Mapped[float] = mapped_column(Float, nullable=False, server_default="8")
    overtimeThreshold: Mapped[float] = mapped_column(Float, nullable=False, server_default="8")
    lateThresholdMinutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="15")
    workStartHour: Mapped[int] = mapped_column(Integer, nullable=False, server_default="9")
    workStartMinute: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    halfDayMaxHours: Mapped[float] = mapped_column(Float, nullable=False, server_default="4")
    absentAfterHour: Mapped[int] = mapped_column(Integer, nullable=False, server_default="18")

    __table_args__ = (
        UniqueConstraint("organizationId", name="workHourPolicy_organizationId_key"),
    )