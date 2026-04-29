import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TimesheetCreate(BaseModel):
    employee_id: uuid.UUID
    project_id: uuid.UUID | None = None
    date: date
    hours: float = Field(gt=0, le=24)
    description: str | None = None


class TimesheetUpdate(BaseModel):
    hours: float | None = Field(default=None, gt=0, le=24)
    description: str | None = None
    status: str | None = None


class TimesheetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    project_id: uuid.UUID | None
    date: date
    hours: float
    description: str | None
    status: str
    created_at: datetime
