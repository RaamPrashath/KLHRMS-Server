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
    MicrosoftManager,
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
MASKED_CREDENTIAL = "xxxx"

MANAGER_CHAIN_MAX_DEPTH = 12


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
        db_settings = await self._repo.get_settings_presence(org_id)
        if db_settings:
            return MicrosoftSettingsResponse(
                tenant_id=MASKED_CREDENTIAL if db_settings["has_tenant_id"] else "",
                client_id=MASKED_CREDENTIAL if db_settings["has_client_id"] else "",
                client_secret=MASKED_CREDENTIAL if db_settings["has_client_secret"] else "",
                is_enabled=db_settings["is_enabled"],
                last_sync_at=db_settings["last_sync_at"],
                last_sync_status=db_settings["last_sync_status"],
                last_sync_summary=db_settings["last_sync_summary"],
            )
        env = get_settings()
        return MicrosoftSettingsResponse(
            tenant_id=MASKED_CREDENTIAL if env.azure_tenant_id else "",
            client_id=MASKED_CREDENTIAL if env.azure_client_id else "",
            client_secret=MASKED_CREDENTIAL if env.azure_client_secret else "",
            is_enabled=bool(env.azure_tenant_id),
        )

    async def save_settings(
        self, org_id: str, tenant_id: str, client_id: str, client_secret: str
    ) -> MicrosoftSettingsResponse:
        existing = await self._repo.get_settings(org_id)
        resolved_tenant = self._resolve_credential_value(
            tenant_id,
            existing.tenant_id if existing else "",
        )
        resolved_client = self._resolve_credential_value(
            client_id,
            existing.client_id if existing else "",
        )
        resolved_secret = self._resolve_credential_value(
            client_secret,
            existing.client_secret if existing else "",
        )

        if not resolved_tenant or not resolved_client or not resolved_secret:
            raise MicrosoftGraphConfigurationError(
                "Tenant ID, Client ID, and Client Secret are required"
            )

        setting = await self._repo.upsert_settings(
            org_id, resolved_tenant, resolved_client, resolved_secret,
        )
        await self._db.commit()
        return MicrosoftSettingsResponse(
            tenant_id=MASKED_CREDENTIAL if setting.tenant_id else "",
            client_id=MASKED_CREDENTIAL if setting.client_id else "",
            client_secret=MASKED_CREDENTIAL if setting.client_secret else "",
            is_enabled=setting.is_enabled,
        )

    async def get_sync_status(self, org_id: str) -> SyncStatusResponse:
        db_settings = await self._repo.get_settings_presence(org_id)
        if not db_settings:
            return SyncStatusResponse(is_configured=False)
        return SyncStatusResponse(
            is_configured=db_settings["is_enabled"],
            tenant_id=MASKED_CREDENTIAL if db_settings["has_tenant_id"] else "",
            client_id=MASKED_CREDENTIAL if db_settings["has_client_id"] else "",
            client_secret_configured=db_settings["has_client_secret"],
            last_sync_at=db_settings["last_sync_at"],
            last_sync_status=db_settings["last_sync_status"],
            last_sync_summary=db_settings["last_sync_summary"],
        )

    def _resolve_credential_value(self, value: str, existing_value: str = "") -> str:
        stripped = value.strip()
        if stripped == MASKED_CREDENTIAL:
            return existing_value or ""
        return stripped or existing_value or ""

    # ── Connection Test (no DB writes) ────────────────────────────────────────

    async def test_connection(
        self, org_id: str, tenant_id: str = "", client_id: str = "", client_secret: str = ""
    ) -> ConnectionTestResult:
        if tenant_id or client_id or client_secret:
            existing = await self._repo.get_settings(org_id)
            resolved_tenant = self._resolve_credential_value(
                tenant_id,
                existing.tenant_id if existing else "",
            )
            resolved_client = self._resolve_credential_value(
                client_id,
                existing.client_id if existing else "",
            )
            resolved_secret = self._resolve_credential_value(
                client_secret,
                existing.client_secret if existing else "",
            )
            if not resolved_tenant or not resolved_client or not resolved_secret:
                raise MicrosoftGraphConfigurationError(
                    "Tenant ID, Client ID, and Client Secret are required"
                )
            tm = TokenManager(resolved_tenant, resolved_client, resolved_secret)
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
                    data["profile_photo_url"] = self._build_profile_photo_url(
                        org_id,
                        gu.graph_id,
                    )
                    await self._repo.update_user_microsoft_image(
                        _user.id,
                        data["profile_photo_url"],
                    )
                    _, employee_created = await self._repo.upsert_employee(org_id, data)
                    await self._repo.link_employee_to_user(
                        org_id, gu.graph_id, _user.id
                    )

                    try:
                        manager_chain = await self._build_manager_chain(client, gu.graph_id)
                        if manager_chain:
                            data["manager_chain"] = manager_chain
                            direct_manager = manager_chain[0] if manager_chain else None
                            if direct_manager and direct_manager.get("graph_id"):
                                manager_emp = await self._repo.find_employee_by_microsoft_id(
                                    org_id, direct_manager["graph_id"]
                                )
                                if manager_emp is not None:
                                    data["manager_id"] = manager_emp.id
                    except Exception as chain_err:
                        logger.warning(
                            "Manager chain lookup failed for %s: %s",
                            gu.email or gu.graph_id,
                            chain_err,
                        )

                    if any(
                        data.get(k) is not None
                        for k in (
                            "manager_chain",
                            "manager_id",
                            "given_name",
                            "surname",
                            "business_phones",
                            "street_address",
                            "city",
                            "state",
                            "postal_code",
                            "country",
                            "company_name",
                            "employee_type",
                            "employee_hire_date",
                            "usage_location",
                            "user_type",
                            "preferred_language",
                            "created_date_time",
                        )
                    ):
                        await self._repo.update_employee_profile(org_id, gu.graph_id, data)

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
            "given_name": gu.given_name,
            "surname": gu.surname,
            "user_principal_name": gu.user_principal_name,
            "email": gu.email or gu.user_principal_name,
            "employee_id": gu.employee_id,
            "department_name": gu.department,
            "job_title": gu.job_title,
            "mobile_phone": gu.mobile_phone,
            "business_phones": gu.business_phones,
            "office_location": gu.office_location,
            "street_address": gu.street_address,
            "city": gu.city,
            "state": gu.state,
            "postal_code": gu.postal_code,
            "country": gu.country,
            "company_name": gu.company_name,
            "employee_type": gu.employee_type,
            "employee_hire_date": gu.employee_hire_date,
            "usage_location": gu.usage_location,
            "user_type": gu.user_type,
            "preferred_language": gu.preferred_language,
            "account_enabled": gu.account_enabled,
            "status": "ACTIVE" if gu.account_enabled else "INACTIVE",
            "created_date_time": gu.created_date_time,
            "synced_at": datetime.now(timezone.utc),
        }

    async def _build_manager_chain(
        self, client: MicrosoftGraphClient, graph_id: str
    ) -> list[dict[str, Any]]:
        """Walk up the manager chain starting from the given user.

        Returns a list ordered from direct manager upward.
        """
        chain: list[dict[str, Any]] = []
        visited: set[str] = set()
        current_id: str | None = graph_id
        for _ in range(MANAGER_CHAIN_MAX_DEPTH):
            if not current_id or current_id in visited:
                break
            visited.add(current_id)
            try:
                manager = await client.get_user_manager(current_id)
            except Exception:
                break
            if manager is None or not manager.graph_id:
                break
            chain.append(
                {
                    "graph_id": manager.graph_id,
                    "display_name": manager.display_name,
                    "user_principal_name": manager.user_principal_name,
                    "job_title": manager.job_title,
                    "department": manager.department,
                    "mail": manager.mail,
                }
            )
            current_id = manager.graph_id
        return chain

    def _build_profile_photo_url(self, org_id: str, microsoft_id: str) -> str:
        return f"/microsoft-graph/profile-photos/{org_id}/{microsoft_id}"

    async def get_profile_photo_bytes(
        self,
        org_id: str,
        microsoft_id: str,
    ) -> bytes | None:
        employee = await self._repo.find_employee_by_microsoft_id(org_id, microsoft_id)
        if employee is None or not employee.profile_photo_url:
            return None

        creds = await self._get_credentials(org_id)
        client = self._build_graph_client(creds)
        return await client.get_user_photo_bytes(microsoft_id)

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
