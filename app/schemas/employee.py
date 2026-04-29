import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class EmployeeCreate(BaseModel):
    user_id: str
    employee_code: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = None
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    designation: str | None = None
    employment_type: str = "full_time"
    date_of_joining: date | None = None
    date_of_birth: date | None = None


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    department_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    designation: str | None = None
    employment_type: str | None = None
    status: str | None = None


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: str
    employee_code: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    department_id: uuid.UUID | None
    manager_id: uuid.UUID | None
    designation: str | None
    employment_type: str
    status: str
    date_of_joining: date | None
    created_at: datetime
