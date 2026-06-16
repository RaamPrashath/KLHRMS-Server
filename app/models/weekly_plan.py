"""Weekly plan model - one row per employee per weekday."""

from datetime import date

from sqlalchemy import Date, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HRMSBase


class WeeklyPlan(HRMSBase):
    __tablename__ = "weekly_plans"

    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    work_location: Mapped[str] = mapped_column(String(40), nullable=False)
    project: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "date",
            name="uq_weekly_plan_org_user_date",
        ),
        Index("idx_weekly_plans_org_date", "organization_id", "date"),
    )
