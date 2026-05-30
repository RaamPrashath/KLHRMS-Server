from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.integrations.microsoft_graph.exceptions import MicrosoftGraphConfigurationError
from app.modules.microsoft_graph.service import MicrosoftIntegrationService


class FakeDb:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


class FakeRepo:
    def __init__(self, existing_settings: object | None = None) -> None:
        self._existing_settings = existing_settings
        self.upsert_settings_args: tuple[str, str, str, str] | None = None
        self.upsert_payloads: list[dict[str, object]] = []
        self.identity_payloads: list[dict[str, object]] = []
        self.summary_args: tuple[str, str, dict[str, int] | None] | None = None
        self.finalize_args: dict[str, int] | None = None
        self.default_role = SimpleNamespace(id="role-employee", name="Employee")
        self.sync_run = SimpleNamespace(
            id="run-1",
            status="in_progress",
            total_fetched=0,
            created_count=0,
            updated_count=0,
            skipped_count=0,
            failed_count=0,
            errors=None,
            started_at=None,
            completed_at=None,
        )

    async def get_settings(self, org_id: str) -> object | None:
        return self._existing_settings

    async def upsert_settings(
        self,
        org_id: str,
        tenant_id: str,
        client_id: str,
        client_secret_ciphertext: str,
    ) -> SimpleNamespace:
        self.upsert_settings_args = (org_id, tenant_id, client_id, client_secret_ciphertext)
        setting = SimpleNamespace(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret_ciphertext=client_secret_ciphertext,
            is_enabled=True,
            last_sync_at=None,
            last_sync_status=None,
            last_sync_summary=None,
        )
        self._existing_settings = setting
        return setting

    async def create_sync_run(self, org_id: str, triggered_by_member_id: str) -> SimpleNamespace:
        return self.sync_run

    async def get_default_member_role(self, org_id: str) -> SimpleNamespace | None:
        return self.default_role

    async def upsert_user_member_from_graph(
        self,
        org_id: str,
        graph_user: SimpleNamespace,
        default_role_id: str,
    ) -> tuple[SimpleNamespace, SimpleNamespace, bool]:
        self.identity_payloads.append(
            {
                "org_id": org_id,
                "graph_id": graph_user.graph_id,
                "email": graph_user.email,
                "display_name": graph_user.display_name,
                "role_id": default_role_id,
            }
        )
        user = SimpleNamespace(
            id="user-1",
            email=(graph_user.email or graph_user.user_principal_name or "").lower(),
            name=graph_user.display_name,
            emailVerified=True,
            onboarded=True,
        )
        member = SimpleNamespace(
            id="member-1",
            organizationId=org_id,
            userId=user.id,
            roleId=default_role_id,
            status="ACTIVE",
        )
        return user, member, True

    async def upsert_employee(self, org_id: str, data: dict[str, object]) -> tuple[SimpleNamespace, bool]:
        self.upsert_payloads.append(data)
        return SimpleNamespace(id="employee-1"), True

    async def finalize_sync_run(
        self,
        run: SimpleNamespace,
        total_fetched: int = 0,
        created_count: int = 0,
        updated_count: int = 0,
        skipped_count: int = 0,
        failed_count: int = 0,
        errors: list[dict[str, object]] | None = None,
    ) -> None:
        self.finalize_args = {
            "total_fetched": total_fetched,
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
        }
        run.status = "success" if failed_count == 0 else "completed_with_errors"
        run.total_fetched = total_fetched
        run.created_count = created_count
        run.updated_count = updated_count
        run.skipped_count = skipped_count
        run.failed_count = failed_count
        run.errors = errors or []
        run.completed_at = datetime.now(timezone.utc)

    async def update_sync_summary(
        self,
        org_id: str,
        status: str,
        summary: dict[str, int] | None = None,
    ) -> None:
        self.summary_args = (org_id, status, summary)


def _build_service(existing_settings: object | None = None) -> tuple[MicrosoftIntegrationService, FakeRepo, FakeDb]:
    service = MicrosoftIntegrationService.__new__(MicrosoftIntegrationService)
    fake_db = FakeDb()
    fake_repo = FakeRepo(existing_settings)
    service._db = fake_db
    service._repo = fake_repo
    return service, fake_repo, fake_db


@pytest.mark.asyncio
async def test_save_settings_persists_encrypted_credentials_and_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    service, fake_repo, fake_db = _build_service()
    monkeypatch.setattr(
        "app.modules.microsoft_graph.service.encrypt_secret",
        lambda value: f"encrypted::{value}",
    )

    response = await service.save_settings("org-1", "tenant-1", "client-1", "secret-1")

    assert fake_repo.upsert_settings_args == (
        "org-1",
        "tenant-1",
        "client-1",
        "encrypted::secret-1",
    )
    assert fake_db.committed is True
    assert response.tenant_id == "tenant-1"
    assert response.client_id == "client-1"
    assert response.client_secret_configured is True
    assert response.is_enabled is True


@pytest.mark.asyncio
async def test_save_settings_requires_secret_on_first_setup() -> None:
    service, fake_repo, fake_db = _build_service()

    with pytest.raises(MicrosoftGraphConfigurationError):
        await service.save_settings("org-1", "tenant-1", "client-1", "")

    assert fake_repo.upsert_settings_args is None
    assert fake_db.committed is False


@pytest.mark.asyncio
async def test_sync_employees_creates_auth_identity_bundle_and_employee_link() -> None:
    service, fake_repo, fake_db = _build_service(
        SimpleNamespace(
            tenant_id="tenant-1",
            client_id="client-1",
            client_secret_ciphertext="ciphertext",
            is_enabled=True,
        )
    )

    graph_user = SimpleNamespace(
        graph_id="graph-user-1",
        display_name="Ada Lovelace",
        user_principal_name="ada.lovelace@example.com",
        email="ada.lovelace@example.com",
        employee_id="EMP-001",
        department="Engineering",
        job_title="Engineering Manager",
        mobile_phone="+1 555 0100",
        office_location="HQ-12",
        account_enabled=True,
    )

    class FakeGraphClient:
        async def get_users(self) -> list[SimpleNamespace]:
            return [graph_user]

    service._get_credentials = AsyncMock(
        return_value={
            "tenant_id": "tenant-1",
            "client_id": "client-1",
            "client_secret": "secret-1",
        }
    )
    service._build_graph_client = lambda _creds: FakeGraphClient()

    response = await service.sync_employees("org-1", "member-1")

    assert fake_db.committed is True
    assert response.total_fetched == 1
    assert response.created_count == 1
    assert response.updated_count == 0
    assert response.failed_count == 0
    assert response.status == "success"
    assert fake_repo.finalize_args == {
        "total_fetched": 1,
        "created_count": 1,
        "updated_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
    }

    payload = fake_repo.upsert_payloads[0]
    assert fake_repo.identity_payloads == [
        {
            "org_id": "org-1",
            "graph_id": "graph-user-1",
            "email": "ada.lovelace@example.com",
            "display_name": "Ada Lovelace",
            "role_id": "role-employee",
        }
    ]
    assert payload["microsoft_id"] == "graph-user-1"
    assert payload["display_name"] == "Ada Lovelace"
    assert payload["user_principal_name"] == "ada.lovelace@example.com"
    assert payload["email"] == "ada.lovelace@example.com"
    assert payload["employee_id"] == "EMP-001"
    assert payload["department_name"] == "Engineering"
    assert payload["job_title"] == "Engineering Manager"
    assert payload["member_id"] == "member-1"
    assert payload["account_enabled"] is True
    assert payload["status"] == "ACTIVE"
    assert payload["synced_at"].tzinfo is not None
    assert "mobile_phone" not in payload
    assert "office_location" not in payload
    assert "profile_photo_url" not in payload
    assert "manager_id" not in payload