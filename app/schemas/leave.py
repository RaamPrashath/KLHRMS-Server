import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LeaveCreate(BaseModel):
    employee_id: uuid.UUID
    leave_type: str
    from_date: date
    to_date: date
    days: float
    reason: str | None = None


class LeaveUpdate(BaseModel):
    status: str | None = None
    approved_by: uuid.UUID | None = None


class LeaveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    leave_type: str
    from_date: date
    to_date: date
    days: float
    status: str
    reason: str | None
    approved_by: uuid.UUID | None
    created_at: datetime
