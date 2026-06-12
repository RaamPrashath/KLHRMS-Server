from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from app.shared.config import get_settings

RESUME_PARSER_BUCKET = "resume-parser"
UPLOADS_DIR = Path(__file__).resolve().parents[3] / ".uploads"


@dataclass(frozen=True)
class ResumeParserUpload:
    bucket: str
    path: str
    public_url: str


def safe_resume_file_stem(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:160] or "resume"


def resume_parser_storage_path(
    *,
    organization_id: str,
    run_id: str,
    file_name: str,
) -> str:
    return "/".join(
        [
            _safe_path_segment(organization_id),
            "resume-parser",
            _safe_path_segment(run_id),
            _safe_path_segment(file_name),
        ]
    )


async def upload_resume_parser_artifact(
    *,
    content: bytes,
    storage_path: str,
    content_type: str,
) -> ResumeParserUpload:
    settings = get_settings()
    supabase_url = settings.supabase_url.rstrip("/")
    bucket = RESUME_PARSER_BUCKET
    is_production = settings.mode.strip().lower() == "production"
    if not supabase_url:
        if not is_production:
            return _write_local_resume_parser_artifact(
                bucket=bucket,
                storage_path=storage_path,
                content=content,
            )
        raise RuntimeError("SUPABASE_URL is not configured")
    if not settings.supabase_service_role_key:
        if not is_production:
            return _write_local_resume_parser_artifact(
                bucket=bucket,
                storage_path=storage_path,
                content=content,
            )
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")

    encoded_path = "/".join(quote(part, safe="") for part in storage_path.split("/"))
    upload_url = f"{supabase_url}/storage/v1/object/{quote(bucket, safe='')}/{encoded_path}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": content_type,
        "x-upsert": "false",
    }
    try:
        await _ensure_resume_parser_bucket(
            supabase_url=supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=bucket,
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(upload_url, headers=headers, content=content)
    except httpx.HTTPError as exc:
        if not is_production:
            return _write_local_resume_parser_artifact(
                bucket=bucket,
                storage_path=storage_path,
                content=content,
            )
        raise RuntimeError("Supabase resume-parser upload failed: network error") from exc
    except RuntimeError:
        if not is_production:
            return _write_local_resume_parser_artifact(
                bucket=bucket,
                storage_path=storage_path,
                content=content,
            )
        raise

    if response.status_code >= 400:
        if not is_production:
            return _write_local_resume_parser_artifact(
                bucket=bucket,
                storage_path=storage_path,
                content=content,
            )
        raise RuntimeError(_storage_error(response))

    public_url = f"{supabase_url}/storage/v1/object/public/{quote(bucket, safe='')}/{encoded_path}"
    return ResumeParserUpload(bucket=bucket, path=storage_path, public_url=public_url)


async def _ensure_resume_parser_bucket(
    *,
    supabase_url: str,
    service_role_key: str,
    bucket: str,
) -> None:
    headers = {
        "Authorization": f"Bearer {service_role_key}",
        "apikey": service_role_key,
        "Content-Type": "application/json",
    }
    encoded_bucket = quote(bucket, safe="")
    async with httpx.AsyncClient(timeout=30.0) as client:
        get_response = await client.get(
            f"{supabase_url}/storage/v1/bucket/{encoded_bucket}",
            headers=headers,
        )
        if get_response.status_code == 200:
            return
        if get_response.status_code != 404 and not _is_bucket_not_found(get_response):
            raise RuntimeError(_storage_error(get_response))

        create_response = await client.post(
            f"{supabase_url}/storage/v1/bucket",
            headers=headers,
            json={"id": bucket, "name": bucket, "public": True},
        )
        if create_response.status_code in {200, 201}:
            return
        if create_response.status_code == 409:
            return
        raise RuntimeError(_storage_error(create_response))


def _is_bucket_not_found(response: httpx.Response) -> bool:
    if response.status_code in {400, 404}:
        try:
            payload = response.json()
        except ValueError:
            return response.status_code == 404
        message = payload.get("message") or payload.get("error")
        return isinstance(message, str) and "bucket not found" in message.lower()
    return False


def _safe_path_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]", "", value).strip()
    return cleaned or "item"


def _write_local_resume_parser_artifact(
    *,
    bucket: str,
    storage_path: str,
    content: bytes,
) -> ResumeParserUpload:
    relative_path = Path(bucket, *storage_path.split("/"))
    target_path = UPLOADS_DIR / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)
    encoded_relative = "/".join(quote(part, safe="") for part in relative_path.as_posix().split("/"))
    return ResumeParserUpload(
        bucket=bucket,
        path=storage_path,
        public_url=f"http://localhost:8000/uploads/{encoded_relative}",
    )


def _storage_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Supabase upload failed with status {response.status_code}"
    message = payload.get("message") or payload.get("error")
    if isinstance(message, str) and message:
        return message
    return f"Supabase upload failed with status {response.status_code}"
