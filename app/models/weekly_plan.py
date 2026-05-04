"""Weekly plan domain model — one row per employee per weekday."""
from datetime import date

from sqlalchemy import Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase
from app.utils.enums import WorkLocationType


class WeeklyPlan(HRMSBase):
    __tablename__ = "weekly_plans"

    # Better Auth user ID — String, no FK (cross-migration-tool boundary)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # The specific calendar date (must be a weekday Mon–Fri, enforced at service layer)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    # Work location for this day
    work_location: Mapped[WorkLocationType] = mapped_column(
        String(20), nullable=False
    )

    # Optional project name / reference (free text)
    project: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "user_id", "date",
            name="uq_weekly_plan_org_user_date",
        ),
    )
