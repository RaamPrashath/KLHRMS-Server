from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MicrosoftAccessToken(BaseModel):
    access_token: str
    expires_at: datetime


class MicrosoftOrganization(BaseModel):
    id: str = ""
    display_name: str = ""
    tenant_branding: list[str] = []


class MicrosoftUser(BaseModel):
    graph_id: str = ""
    display_name: str = ""
    user_principal_name: str | None = None
    email: str | None = None
    employee_id: str | None = None
    department: str | None = None
    job_title: str | None = None
    account_enabled: bool = True


class MicrosoftManager(BaseModel):
    graph_id: str = ""
    display_name: str = ""


class MicrosoftGroup(BaseModel):
    graph_id: str = ""
    display_name: str = ""
    description: str | None = None
    group_type: str | None = None


class ConnectionTestResult(BaseModel):
    connected: bool
    tenant_name: str = ""
    tenant_id: str = ""
    error: str | None = None
