import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class AttendanceCreate(BaseModel):
    employee_id: uuid.UUID
    date: date
    check_in: datetime | None = None
    check_out: datetime | None = None
    status: str = "present"
    source: str = "manual"
    notes: str | None = None


class AttendanceUpdate(BaseModel):
    check_in: datetime | None = None
    check_out: datetime | None = None
    status: str | None = None
    notes: str | None = None


class AttendanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    date: date
    check_in: datetime | None
    check_out: datetime | None
    status: str
    source: str
    notes: str | None
    created_at: datetime
