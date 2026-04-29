import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HRMSRoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    organization_id: uuid.UUID
    role: str
    permissions: dict
    is_active: bool
    created_at: datetime
