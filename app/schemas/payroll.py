import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class PayrollCreate(BaseModel):
    period_month: int
    period_year: int


class PayrollRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    period_month: int
    period_year: int
    status: str
    total_gross: float
    total_deductions: float
    total_net: float
    processed_at: date | None
    created_at: datetime
