"""
Organization schemas.
The organization record itself lives in Better Auth's DB.
FastAPI only reads organization_id from the auth context.
These schemas represent HRMS-side org configuration.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrganizationSettings(BaseModel):
    """HRMS-specific settings stored per organization."""
    organization_id: uuid.UUID
    timezone: str = "UTC"
    currency: str = "USD"
    working_days: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    fiscal_year_start_month: int = 1  # January
