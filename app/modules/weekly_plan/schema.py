"""Weekly plan request/response schemas."""
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.utils.enums import WorkLocationType


class WeeklyPlanCreate(BaseModel):
    work_location: WorkLocationType
    project: str | None = Field(default=None, max_length=200)

    @field_validator("project")
    @classmethod
    def strip_project(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("project must be a string")
        return v.strip()


class WeeklyPlanDayCreate(WeeklyPlanCreate):
    """Used for PUT /weekly-plans/{date} — date comes from the path."""

    @staticmethod
    def validate_weekday(d: date) -> date:
        if d.weekday() >= 5:
            raise ValueError(
                "Weekly plans are only supported for weekdays (Monday–Friday)"
            )
        return d


class WeeklyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: str
    user_name: str | None = None
    date: date
    work_location: WorkLocationType
    project: str | None
