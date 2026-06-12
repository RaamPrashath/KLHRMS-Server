from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote
from uuid import uuid4

import httpx

from app.shared.config import get_settings


@dataclass(frozen=True)
class OfferPdfUpload:
    bucket: str
    path: str
    public_url: str


def safe_offer_file_name(candidate_name: str, job_title: str) -> str:
    base_name = f"{candidate_name.strip()} - {job_title.strip()} Offer Letter".strip(" -")
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", base_name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip() or "Offer Letter"
    return f"{cleaned[:240]}.pdf"


def offer_storage_path(
    *,
    organization_id: str,
    job_posting_id: str,
    application_id: str,
    offer_letter_id: str,
    file_name: str,
) -> str:
    return "/".join(
        [
            _safe_path_segment(organization_id),
            "offers",
            _safe_path_segment(job_posting_id),
            _safe_path_segment(application_id),
            _safe_path_segment(offer_letter_id),
            _safe_path_segment(file_name),
        ]
    )


def offer_template_asset_storage_path(
    *,
    organization_id: str,
    template_id: str,
    extension: str,
) -> str:
    return "/".join(
        [
            _safe_path_segment(organization_id),
            "offers",
            "templates",
            _safe_path_segment(template_id),
            "assets",
            f"{uuid4().hex}{extension}",
        ]
    )


async def upload_offer_pdf(pdf: bytes, storage_path: str) -> OfferPdfUpload:
    """Upload via Supabase Storage REST using the service role key."""

    return await upload_offer_file(
        content=pdf,
        storage_path=storage_path,
        content_type="application/pdf",
        upsert=False,
    )


async def upload_offer_file(
    *,
    content: bytes,
    storage_path: str,
    content_type: str,
    upsert: bool = False,
) -> OfferPdfUpload:
    """Upload offer artifacts directly to the public Supabase offer bucket."""

    settings = get_settings()
    supabase_url = settings.supabase_url.rstrip("/")
    bucket = settings.supabase_offer_bucket.strip() or "offer-letter"
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")

    encoded_path = "/".join(quote(part, safe="") for part in storage_path.split("/"))
    upload_url = f"{supabase_url}/storage/v1/object/{quote(bucket, safe='')}/{encoded_path}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": content_type,
        "x-upsert": "true" if upsert else "false",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(upload_url, headers=headers, content=content)
    except httpx.HTTPError as exc:
        raise RuntimeError("Supabase offer upload failed: network error") from exc

    if response.status_code >= 400:
        raise RuntimeError(_storage_error(response))

    public_url = f"{supabase_url}/storage/v1/object/public/{quote(bucket, safe='')}/{encoded_path}"
    return OfferPdfUpload(bucket=bucket, path=storage_path, public_url=public_url)


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
