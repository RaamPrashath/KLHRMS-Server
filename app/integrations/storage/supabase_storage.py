from __future__ import annotations

from urllib.parse import quote

import httpx

from app.shared.config import get_settings


class SupabaseStorageError(RuntimeError):
    pass


async def upload_private_file(
    *,
    bucket: str,
    path: str,
    content: bytes,
    content_type: str,
) -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SupabaseStorageError("Supabase storage is not configured")

    encoded_path = quote(path, safe="/")
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{encoded_path}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "apikey": settings.supabase_service_role_key,
                    "Content-Type": content_type,
                    "x-upsert": "false",
                },
                content=content,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise SupabaseStorageError("Failed to upload file to Supabase storage") from exc
