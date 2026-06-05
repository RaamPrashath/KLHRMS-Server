from datetime import date, datetime
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
    given_name: str | None = None
    surname: str | None = None
    user_principal_name: str | None = None
    email: str | None = None
    employee_id: str | None = None
    department: str | None = None
    job_title: str | None = None
    mobile_phone: str | None = None
    business_phones: list[str] | None = None
    office_location: str | None = None
    street_address: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    company_name: str | None = None
    employee_type: str | None = None
    employee_hire_date: date | None = None
    usage_location: str | None = None
    user_type: str | None = None
    preferred_language: str | None = None
    account_enabled: bool = True
    created_date_time: datetime | None = None


class MicrosoftManager(BaseModel):
    graph_id: str = ""
    display_name: str = ""
    user_principal_name: str | None = None
    job_title: str | None = None
    mail: str | None = None
    department: str | None = None


class MicrosoftDirectReport(BaseModel):
    graph_id: str = ""
    display_name: str = ""
    job_title: str | None = None
    department: str | None = None
    mail: str | None = None
    account_enabled: bool = True


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
