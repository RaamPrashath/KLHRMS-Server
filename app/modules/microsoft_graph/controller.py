import logging

from app.integrations.microsoft_graph.schema import ConnectionTestResult, MicrosoftOrganization
from app.modules.microsoft_graph.schema import (
    MicrosoftSettingsResponse,
    SyncRunListItem,
    SyncRunResponse,
    SyncStatusResponse,
)
from app.modules.microsoft_graph.service import MicrosoftIntegrationService

logger = logging.getLogger("klhrms.microsoft.graph.controller")


class MicrosoftGraphController:
    """Thin orchestration — delegates to service."""

    def __init__(self, service: MicrosoftIntegrationService) -> None:
        self._service = service

    async def get_settings(self, org_id: str) -> MicrosoftSettingsResponse:
        return await self._service.get_settings(org_id)

    async def save_settings(
        self, org_id: str, tenant_id: str, client_id: str, client_secret: str
    ) -> MicrosoftSettingsResponse:
        return await self._service.save_settings(org_id, tenant_id, client_id, client_secret)

    async def test_connection(
        self, org_id: str, tenant_id: str = "", client_id: str = "", client_secret: str = ""
    ) -> ConnectionTestResult:
        return await self._service.test_connection(org_id, tenant_id, client_id, client_secret)

    async def get_organization(self, org_id: str) -> MicrosoftOrganization:
        return await self._service.get_organization(org_id)

    async def sync_employees(
        self, org_id: str, triggered_by_member_id: str
    ) -> SyncRunResponse:
        return await self._service.sync_employees(org_id, triggered_by_member_id)

    async def get_sync_runs(
        self, org_id: str, limit: int = 20, offset: int = 0
    ) -> list[SyncRunListItem]:
        return await self._service.get_sync_runs(org_id, limit, offset)

    async def get_sync_run(self, org_id: str, run_id: str) -> SyncRunResponse | None:
        return await self._service.get_sync_run(org_id, run_id)

    async def get_sync_status(self, org_id: str) -> SyncStatusResponse:
        return await self._service.get_sync_status(org_id)
