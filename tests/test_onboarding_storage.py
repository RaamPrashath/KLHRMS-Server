from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.modules.onboarding import storage


@pytest.mark.asyncio
async def test_onboarding_upload_production_network_error_is_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def post(self, *args: object, **kwargs: object) -> httpx.Response:
            request = httpx.Request("POST", "https://supabase.example/storage/v1/object")
            raise httpx.ConnectError("getaddrinfo failed", request=request)

    monkeypatch.setattr(storage.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        storage,
        "get_settings",
        lambda: SimpleNamespace(
                supabase_url="https://supabase.example",
                supabase_service_role_key="service-role-key",
                supabase_onboarding_bucket="onboarding-documents",
                mode="production",
            ),
        )

    with pytest.raises(RuntimeError, match="Supabase onboarding upload failed: network error"):
        await storage.upload_onboarding_document(
            file_base64="cGRm",
            storage_path="org/onboarding/test.pdf",
            content_type="application/pdf",
        )
