from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MicrosoftSettingsSaveRequest(BaseModel):
    tenant_id: str = Field("", min_length=0)
    client_id: str = Field("", min_length=0)
    client_secret: str = Field("", min_length=0)


class MicrosoftSettingsResponse(BaseModel):
    tenant_id: str = ""
    client_id: str = ""
    client_secret_configured: bool = False
    is_enabled: bool = False
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_summary: dict[str, Any] | None = None


class SyncRunResponse(BaseModel):
    id: str
    status: str
    total_fetched: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    errors: list[dict[str, Any]] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SyncRunListItem(BaseModel):
    id: str
    status: str
    total_fetched: int = 0
    created_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    has_errors: bool = False


class TestConnectionRequest(BaseModel):
    tenant_id: str = Field("", min_length=0)
    client_id: str = Field("", min_length=0)
    client_secret: str = Field("", min_length=0)


class SyncStatusResponse(BaseModel):
    is_configured: bool
    tenant_id: str = ""
    client_id: str = ""
    client_secret_configured: bool = False
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_summary: dict[str, Any] | None = None
