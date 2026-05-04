"""Weekly plan request/response schemas."""
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.enums import WorkLocationType


class WeeklyPlanCreate(BaseModel):
    work_location: WorkLocationType
    project: str | None = Field(default=None, max_length=200)

    @field_validator("project")
    @classmethod
    def strip_project(cls, v: str | None) -> str | None:
        return v.strip() if v else None


class WeeklyPlanDayCreate(WeeklyPlanCreate):
    """Used for the PUT /weekly-plans/{date} endpoint — date comes from the path."""

    @staticmethod
    def validate_weekday(d: date) -> date:
        if d.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            raise ValueError(
                "Weekly plans are only supported for weekdays (Monday–Friday)"
            )
        return d


class WeeklyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:            uuid.UUID
    organization_id: uuid.UUID
    user_id:       str
    date:          date
    work_location: WorkLocationType
    project:       str | None
