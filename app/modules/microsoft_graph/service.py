import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.microsoft_graph.exceptions import (
    MicrosoftGraphConfigurationError,
)
from app.integrations.microsoft_graph.graph_client import MicrosoftGraphClient
from app.integrations.microsoft_graph.schema import (
    ConnectionTestResult,
    MicrosoftOrganization,
    MicrosoftUser,
)
from app.integrations.microsoft_graph.token_manager import TokenManager
from app.modules.microsoft_graph.repository import MicrosoftGraphRepository
from app.modules.microsoft_graph.schema import (
    MicrosoftSettingsResponse,
    SyncRunListItem,
    SyncRunResponse,
    SyncStatusResponse,
)
from app.shared.config import get_settings

logger = logging.getLogger("klhrms.microsoft.graph.service")


class MicrosoftIntegrationService:
    """Business logic for Microsoft Graph integration."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = MicrosoftGraphRepository(db)

    async def _get_credentials(self, org_id: str) -> dict[str, str]:
        """Resolve credentials: DB settings first, env var fallback."""
        db_settings = await self._repo.get_settings(org_id)
        if db_settings and db_settings.is_enabled and db_settings.client_secret:
            return {
                "tenant_id": db_settings.tenant_id,
                "client_id": db_settings.client_id,
                "client_secret": db_settings.client_secret,
            }
        env = get_settings()
        if env.azure_tenant_id and env.azure_client_id and env.azure_client_secret:
            return {
                "tenant_id": env.azure_tenant_id,
                "client_id": env.azure_client_id,
                "client_secret": env.azure_client_secret,
            }
        raise MicrosoftGraphConfigurationError(
            "Microsoft Graph not configured — set credentials in settings or env vars"
        )

    def _build_graph_client(self, creds: dict[str, str]) -> MicrosoftGraphClient:
        tm = TokenManager(creds["tenant_id"], creds["client_id"], creds["client_secret"])
        return MicrosoftGraphClient(tm)

    # ── Settings ───────────────────────────────────────────────────────────────

    async def get_settings(self, org_id: str) -> MicrosoftSettingsResponse:
        db_settings = await self._repo.get_settings(org_id)
        if db_settings:
            return MicrosoftSettingsResponse(
                tenant_id=db_settings.tenant_id,
                client_id=db_settings.client_id,
                client_secret=db_settings.client_secret or "",
                is_enabled=db_settings.is_enabled,
                last_sync_at=db_settings.last_sync_at,
                last_sync_status=db_settings.last_sync_status,
                last_sync_summary=db_settings.last_sync_summary,
            )
        env = get_settings()
        return MicrosoftSettingsResponse(
            tenant_id=env.azure_tenant_id or "",
            client_id=env.azure_client_id or "",
            client_secret=env.azure_client_secret or "",
            is_enabled=bool(env.azure_tenant_id),
        )

    async def save_settings(
        self, org_id: str, tenant_id: str, client_id: str, client_secret: str
    ) -> MicrosoftSettingsResponse:
        existing = await self._repo.get_settings(org_id)
        resolved_tenant = tenant_id.strip() or (existing.tenant_id if existing else "")
        resolved_client = client_id.strip() or (existing.client_id if existing else "")
        resolved_secret = client_secret.strip() or (existing.client_secret if existing else "")

        if not resolved_tenant or not resolved_client or not resolved_secret:
            raise MicrosoftGraphConfigurationError(
                "Tenant ID, Client ID, and Client Secret are required"
            )

        setting = await self._repo.upsert_settings(
            org_id, resolved_tenant, resolved_client, resolved_secret,
        )
        await self._db.commit()
        return MicrosoftSettingsResponse(
            tenant_id=setting.tenant_id,
            client_id=setting.client_id,
            client_secret=setting.client_secret or "",
            is_enabled=setting.is_enabled,
        )

    async def get_sync_status(self, org_id: str) -> SyncStatusResponse:
        db_settings = await self._repo.get_settings(org_id)
        if not db_settings:
            return SyncStatusResponse(is_configured=False)
        return SyncStatusResponse(
            is_configured=db_settings.is_enabled,
            tenant_id=db_settings.tenant_id,
            client_id=db_settings.client_id,
            client_secret_configured=bool(db_settings.client_secret),
            last_sync_at=db_settings.last_sync_at,
            last_sync_status=db_settings.last_sync_status,
            last_sync_summary=db_settings.last_sync_summary,
        )

    # ── Connection Test (no DB writes) ────────────────────────────────────────

    async def test_connection(
        self, org_id: str, tenant_id: str = "", client_id: str = "", client_secret: str = ""
    ) -> ConnectionTestResult:
        if tenant_id and client_id and client_secret:
            tm = TokenManager(tenant_id.strip(), client_id.strip(), client_secret.strip())
            client = MicrosoftGraphClient(tm)
        else:
            creds = await self._get_credentials(org_id)
            client = self._build_graph_client(creds)
        return await client.test_connection()

    # ── Organization ───────────────────────────────────────────────────────────

    async def get_organization(self, org_id: str) -> MicrosoftOrganization:
        creds = await self._get_credentials(org_id)
        client = self._build_graph_client(creds)
        return await client.get_organization()

    # ── Employee Sync ──────────────────────────────────────────────────────────

    async def sync_employees(
        self, org_id: str, triggered_by_member_id: str
    ) -> SyncRunResponse:
        creds = await self._get_credentials(org_id)
        client = self._build_graph_client(creds)
        default_role = await self._repo.get_default_member_role(org_id)
        if default_role is None:
            raise MicrosoftGraphConfigurationError(
                "At least one organization role is required before Microsoft users can be synced"
            )

        sync_run = await self._repo.create_sync_run(org_id, triggered_by_member_id)

        try:
            graph_users = await client.get_users()
            total_fetched = len(graph_users)
            created_count = 0
            updated_count = 0
            skipped_count = 0
            failed_count = 0
            errors: list[dict[str, Any]] = []

            logger.info(
                "Syncing %d users from Microsoft Graph for org %s",
                total_fetched,
                org_id,
            )

            for gu in graph_users:
                try:
                    _user, member, identity_created = await self._repo.upsert_user_member_from_graph(
                        org_id,
                        gu,
                        default_role.id,
                    )
                    data = self._map_graph_user(gu)
                    data["member_id"] = str(member.id)
                    _, employee_created = await self._repo.upsert_employee(org_id, data)
                    if identity_created or employee_created:
                        created_count += 1
                    else:
                        updated_count += 1
                except Exception as e:
                    failed_count += 1
                    email = gu.email or gu.user_principal_name or "unknown"
                    errors.append({"email": email, "error": str(e)})
                    logger.error("Failed to sync user %s: %s", email, e)

            await self._repo.finalize_sync_run(
                sync_run,
                total_fetched=total_fetched,
                created_count=created_count,
                updated_count=updated_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                errors=errors,
            )
            await self._repo.update_sync_summary(
                org_id,
                status="success" if failed_count == 0 else "completed_with_errors",
                summary={
                    "total": total_fetched,
                    "created": created_count,
                    "updated": updated_count,
                    "skipped": skipped_count,
                    "failed": failed_count,
                },
            )

            logger.info(
                "Sync complete: %d created, %d updated, %d failed",
                created_count,
                updated_count,
                failed_count,
            )

        except Exception as e:
            sync_run.status = "failed"
            sync_run.completed_at = datetime.now(timezone.utc)
            logger.error("Sync failed: %s", e)
            await self._repo.update_sync_summary(org_id, status="failed")
            raise

        await self._db.commit()
        return self._run_to_response(sync_run)

    def _map_graph_user(self, gu: MicrosoftUser) -> dict[str, Any]:
        return {
            "microsoft_id": gu.graph_id,
            "display_name": gu.display_name,
            "user_principal_name": gu.user_principal_name,
            "email": gu.email or gu.user_principal_name,
            "employee_id": gu.employee_id,
            "department_name": gu.department,
            "job_title": gu.job_title,
            "account_enabled": gu.account_enabled,
            "status": "ACTIVE" if gu.account_enabled else "INACTIVE",
            "synced_at": datetime.now(timezone.utc),
        }

    # ── Sync Runs ──────────────────────────────────────────────────────────────

    async def get_sync_runs(
        self, org_id: str, limit: int = 20, offset: int = 0
    ) -> list[SyncRunListItem]:
        runs = await self._repo.get_sync_runs(org_id, limit, offset)
        return [
            SyncRunListItem(
                id=str(r.id),
                status=r.status,
                total_fetched=r.total_fetched,
                created_count=r.created_count,
                updated_count=r.updated_count,
                failed_count=r.failed_count,
                started_at=r.started_at,
                completed_at=r.completed_at,
                has_errors=bool(r.errors),
            )
            for r in runs
        ]

    async def get_sync_run(
        self, org_id: str, run_id: str
    ) -> SyncRunResponse | None:
        run = await self._repo.get_sync_run(org_id, run_id)
        if not run:
            return None
        return self._run_to_response(run)

    def _run_to_response(self, run) -> SyncRunResponse:
        return SyncRunResponse(
            id=str(run.id),
            status=run.status,
            total_fetched=run.total_fetched,
            created_count=run.created_count,
            updated_count=run.updated_count,
            skipped_count=run.skipped_count,
            failed_count=run.failed_count,
            errors=run.errors,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
