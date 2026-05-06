"""Weekly plan request/response schemas."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.weekly_plan.locations import PLAN_LOCATION_OPTIONS, PlanLocationValue


def validate_weekday(value: date) -> date:
    if value.weekday() >= 5:
        raise ValueError("Weekly plans are only supported for weekdays (Monday-Friday)")
    return value


class PlanLocationOptionRead(BaseModel):
    value: PlanLocationValue
    label: str
    short_label: str
    color: str


class WeeklyPlanDayWrite(BaseModel):
    date: date
    work_location: PlanLocationValue | None = None
    project: str | None = Field(default=None, max_length=200)

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: date) -> date:
        return validate_weekday(value)

    @field_validator("project")
    @classmethod
    def strip_project(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class WeeklyPlanDayCreate(BaseModel):
    work_location: PlanLocationValue
    project: str | None = Field(default=None, max_length=200)

    @field_validator("project")
    @classmethod
    def strip_project(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class WeeklyPlanBulkSaveRequest(BaseModel):
    days: list[WeeklyPlanDayWrite] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_dates(self) -> "WeeklyPlanBulkSaveRequest":
        dates = [day.date for day in self.days]
        if len(dates) != len(set(dates)):
            raise ValueError("Each plan date may only be submitted once per request")
        return self


class WeeklyPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: str
    user_name: str | None = None
    date: date
    work_location: PlanLocationValue
    project: str | None


def build_location_options() -> list[PlanLocationOptionRead]:
    return [PlanLocationOptionRead(**option) for option in PLAN_LOCATION_OPTIONS]
