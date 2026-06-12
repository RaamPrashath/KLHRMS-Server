from __future__ import annotations

import re
from base64 import b64decode
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from app.shared.config import get_settings


@dataclass(frozen=True)
class OnboardingDocUpload:
    bucket: str
    path: str
    public_url: str


def onboarding_document_storage_path(
    *,
    organization_id: str,
    application_id: str,
    record_id: str,
    document_type: str,
    file_name: str,
) -> str:
    return "/".join(
        [
            _safe_path_segment(organization_id),
            "onboarding",
            _safe_path_segment(application_id),
            _safe_path_segment(record_id),
            _safe_path_segment(file_name),
        ]
    )


async def upload_onboarding_document(
    *,
    file_base64: str,
    storage_path: str,
    content_type: str,
) -> OnboardingDocUpload:
    settings = get_settings()
    supabase_url = settings.supabase_url.rstrip("/")
    bucket = settings.supabase_onboarding_bucket.strip() or "onboarding-documents"
    content = _decode_file_base64(file_base64)
    if not supabase_url:
        if settings.mode.strip().lower() != "production":
            return _write_local_onboarding_document(bucket=bucket, storage_path=storage_path, content=content)
        raise RuntimeError("SUPABASE_URL is not configured")
    if not settings.supabase_service_role_key:
        if settings.mode.strip().lower() != "production":
            return _write_local_onboarding_document(bucket=bucket, storage_path=storage_path, content=content)
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")

    encoded_path = "/".join(quote(part, safe="") for part in storage_path.split("/"))
    upload_url = f"{supabase_url}/storage/v1/object/{quote(bucket, safe='')}/{encoded_path}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(upload_url, headers=headers, content=content)
    except httpx.HTTPError as exc:
        if settings.mode.strip().lower() != "production":
            return _write_local_onboarding_document(bucket=bucket, storage_path=storage_path, content=content)
        raise RuntimeError("Supabase onboarding upload failed: network error") from exc

    if response.status_code >= 400:
        if settings.mode.strip().lower() != "production":
            return _write_local_onboarding_document(bucket=bucket, storage_path=storage_path, content=content)
        raise RuntimeError(_storage_error(response))

    public_url = f"{supabase_url}/storage/v1/object/public/{quote(bucket, safe='')}/{encoded_path}"
    return OnboardingDocUpload(bucket=bucket, path=storage_path, public_url=public_url)


def _decode_file_base64(file_base64: str) -> bytes:
    payload = file_base64.split(",", 1)[1] if file_base64.startswith("data:") and "," in file_base64 else file_base64
    return b64decode(payload)


def _write_local_onboarding_document(*, bucket: str, storage_path: str, content: bytes) -> OnboardingDocUpload:
    uploads_dir = Path(__file__).resolve().parents[3] / ".uploads"
    relative_path = Path(bucket, *storage_path.split("/"))
    target_path = uploads_dir / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)
    encoded_relative = "/".join(quote(part, safe="") for part in relative_path.as_posix().split("/"))
    return OnboardingDocUpload(
        bucket=bucket,
        path=storage_path,
        public_url=f"http://localhost:8000/uploads/{encoded_relative}",
    )


def _safe_path_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "", value).strip()
    return cleaned or "item"


def _storage_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Supabase upload failed with status {response.status_code}"
    message = payload.get("message") or payload.get("error")
    if isinstance(message, str) and message:
        return message
    return f"Supabase upload failed with status {response.status_code}"
