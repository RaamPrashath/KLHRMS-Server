from __future__ import annotations

from urllib.parse import quote

import httpx

from app.shared.config import get_settings


class SupabaseStorageError(RuntimeError):
    pass


def _extract_supabase_error_message(response: httpx.Response, fallback: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for key in ("message", "error", "msg"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return f"{fallback} ({response.status_code}): {value.strip()}"
        return f"{fallback} ({response.status_code})"

    text = response.text.strip()
    if text:
        return f"{fallback} ({response.status_code}): {text[:400]}"
    return f"{fallback} ({response.status_code})"


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
            if response.is_error:
                raise SupabaseStorageError(
                    _extract_supabase_error_message(
                        response,
                        f"Failed to upload file to Supabase storage bucket '{bucket}' at '{path}'",
                    )
                )
    except httpx.HTTPError as exc:
        raise SupabaseStorageError("Failed to upload file to Supabase storage: network error") from exc


async def create_private_file_signed_url(
    *,
    bucket: str,
    path: str,
    expires_in: int = 300,
) -> str:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SupabaseStorageError("Supabase storage is not configured")

    encoded_path = quote(path, safe="/")
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/{bucket}/{encoded_path}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "apikey": settings.supabase_service_role_key,
                    "Content-Type": "application/json",
                },
                json={"expiresIn": expires_in},
            )
            if response.is_error:
                raise SupabaseStorageError(
                    _extract_supabase_error_message(
                        response,
                        f"Failed to create signed URL for bucket '{bucket}' at '{path}'",
                    )
                )
            payload = response.json()
    except httpx.HTTPError as exc:
        raise SupabaseStorageError("Failed to create signed file URL: network error") from exc

    signed_url = payload.get("signedURL")
    if not isinstance(signed_url, str) or not signed_url.strip():
        raise SupabaseStorageError("Supabase storage returned an invalid signed URL")
    if signed_url.startswith("http://") or signed_url.startswith("https://"):
        return signed_url
    return f"{settings.supabase_url.rstrip('/')}/storage/v1{signed_url}"


async def download_private_file(*, bucket: str, path: str) -> bytes:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SupabaseStorageError("Supabase storage is not configured")

    encoded_path = quote(path, safe="/")
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{encoded_path}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                    "apikey": settings.supabase_service_role_key,
                },
            )
            if response.is_error:
                raise SupabaseStorageError(
                    _extract_supabase_error_message(
                        response,
                        f"Failed to download file from bucket '{bucket}' at '{path}'",
                    )
                )
            return response.content
    except httpx.HTTPError as exc:
        raise SupabaseStorageError("Failed to download file from Supabase storage: network error") from exc
