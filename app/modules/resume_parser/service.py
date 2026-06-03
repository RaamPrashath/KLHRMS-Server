from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any

import httpx
from fastapi import HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.models.resume_parser import ResumeParserHistory
from app.models.user import User
from app.modules.ai_scoring.extractor import detect_resume_file_type, extract_resume_text
from app.modules.resume_parser.render import create_resume_docx
from app.modules.resume_parser.schema import (
    ResumeParserFileRead,
    ResumeParserHistoryRead,
    ResumeParserHistoryResponse,
    ResumeParserProcessResponse,
    TemplateType,
)
from app.modules.resume_parser.storage import (
    resume_parser_storage_path,
    safe_resume_file_stem,
    upload_resume_parser_artifact,
)
from app.shared.config import get_settings

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_RESUME_BYTES = 10 * 1024 * 1024
MAX_MODEL_INPUT_CHARS = 30000


async def process_resume_files(
    *,
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    files: list[UploadFile],
    template_type: TemplateType,
) -> ResumeParserProcessResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one resume")

    run_id = uuid.uuid4().hex
    processed: list[ResumeParserFileRead] = []
    for file in files:
        result = await _process_one_file(
            organization_id=organization_id,
            run_id=run_id,
            file=file,
            template_type=template_type,
        )
        processed.append(result)
        db.add(
            ResumeParserHistory(
                organizationId=organization_id,
                memberId=member_id,
                originalFilename=result.originalFilename,
                templateType=template_type,
                status=result.status,
                messages=result.messages,
                jsonUrl=result.jsonUrl,
                docxUrl=result.docxUrl,
            )
        )
    await db.commit()
    return ResumeParserProcessResponse(processedFiles=processed)


async def list_resume_parser_history(
    *,
    db: AsyncSession,
    organization_id: str,
    member_id: str,
    scope: str | None,
    limit: int = 100,
) -> ResumeParserHistoryResponse:
    safe_limit = min(max(limit, 1), 200)
    is_organization_scope = scope == "organization"
    query = (
        select(ResumeParserHistory, User.name)
        .join(Member, ResumeParserHistory.memberId == Member.id)
        .join(User, Member.userId == User.id)
        .where(ResumeParserHistory.organizationId == organization_id)
        .order_by(desc(ResumeParserHistory.createdAt))
        .limit(safe_limit)
    )
    if not is_organization_scope:
        query = query.where(ResumeParserHistory.memberId == member_id)

    result = await db.execute(
        query
    )
    items = [
        ResumeParserHistoryRead(
            id=item.id,
            uploaderName=uploader_name,
            originalFilename=item.originalFilename,
            status=item.status,
            createdAt=item.createdAt,
            jsonUrl=item.jsonUrl,
            docxUrl=item.docxUrl,
            messages=item.messages,
        )
        for item, uploader_name in result.all()
    ]
    return ResumeParserHistoryResponse(
        scope="organization" if is_organization_scope else "self",
        items=items,
    )


async def _process_one_file(
    *,
    organization_id: str,
    run_id: str,
    file: UploadFile,
    template_type: TemplateType,
) -> ResumeParserFileRead:
    original_filename = file.filename or "resume"
    messages: list[str] = []
    try:
        content = await file.read(MAX_RESUME_BYTES + 1)
        if len(content) > MAX_RESUME_BYTES:
            raise ValueError("Resume must be 10 MB or smaller")
        file_type = detect_resume_file_type(original_filename, file.content_type, content)
        if file_type == "unsupported":
            raise ValueError("Only PDF, DOCX, and DOC resumes are supported")

        extraction = extract_resume_text(content, file_type)
        resume_data = await parse_resume_to_generation_json(extraction.sanitized_text)
        messages.append("Resume parsed successfully")

        stem = safe_resume_file_stem(original_filename)
        json_bytes = json.dumps(resume_data, indent=2, ensure_ascii=False).encode("utf-8")
        docx_bytes = create_resume_docx(resume_data, template_type)

        json_upload = await upload_resume_parser_artifact(
            content=json_bytes,
            storage_path=resume_parser_storage_path(
                organization_id=organization_id,
                run_id=run_id,
                file_name=f"{stem}.json",
            ),
            content_type="application/json",
        )
        docx_upload = await upload_resume_parser_artifact(
            content=docx_bytes,
            storage_path=resume_parser_storage_path(
                organization_id=organization_id,
                run_id=run_id,
                file_name=f"{stem}.docx",
            ),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        messages.append("Enhanced resume generated successfully")
        return ResumeParserFileRead(
            originalFilename=original_filename,
            jsonUrl=json_upload.public_url,
            docxUrl=docx_upload.public_url,
            status="success",
            messages=messages,
        )
    except Exception as exc:
        return ResumeParserFileRead(
            originalFilename=original_filename,
            status="failed",
            messages=[*messages, str(exc)],
        )


async def parse_resume_to_generation_json(resume_text: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    if not resume_text.strip():
        raise RuntimeError("Resume text extraction returned no usable text")

    prompt = _build_prompt(resume_text)
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    url = GEMINI_ENDPOINT.format(model=settings.gemini_model)
    response = await _call_gemini_with_retry(
        url=url,
        api_key=settings.gemini_api_key,
        payload=payload,
    )

    data = json.loads(_strip_json_fence(_extract_response_text(response.json())))
    return _normalize_resume_data(data)


async def _call_gemini_with_retry(
    *,
    url: str,
    api_key: str,
    payload: dict[str, Any],
) -> httpx.Response:
    retry_statuses = {429, 500, 502, 503, 504}
    last_status: int | None = None
    for attempt, delay_seconds in enumerate((0.0, 1.5, 3.0, 6.0), start=1):
        if delay_seconds:
            await asyncio.sleep(delay_seconds)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params={"key": api_key}, json=payload)
            if response.status_code not in retry_statuses:
                response.raise_for_status()
                return response
            last_status = response.status_code
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code not in retry_statuses:
                raise RuntimeError(f"Gemini request failed with status {status_code}") from exc
            last_status = status_code
        except httpx.HTTPError as exc:
            if attempt == 4:
                raise RuntimeError("Gemini request failed due to a network error") from exc

    status_text = f"status {last_status}" if last_status is not None else "a temporary error"
    raise RuntimeError(f"Gemini is temporarily unavailable ({status_text}). Please try again.")


def _build_prompt(resume_text: str) -> str:
    contract = {
        "personal_info": {
            "name": "string",
            "email": "string or null",
            "phone": "string or null",
            "linkedin": "string or null",
            "portfolio_url": "string or null",
        },
        "summary": ["exactly 10 concise resume-supported professional summary bullets"],
        "experience": [
            {
                "title": "string",
                "company": "string",
                "dates": "string",
                "client": "string or null",
                "project": "string or null",
                "project_desc": "string or null",
                "technologies": ["string"],
                "responsibilities": ["string"],
            }
        ],
        "education": [{"degree": "string", "school": "string", "dates": "string"}],
        "skills": ["string"],
        "awards": ["string"],
        "projects": [
            {
                "client": "string",
                "project": "string",
                "project_desc": "string",
                "technologies": ["string"],
                "responsibilities": ["string"],
            }
        ],
        "additional_info": {
            "areas_of_expertise": ["string"],
            "business_overview": "string",
        },
    }
    return (
        "Parse this resume into JSON for a professional resume generator. "
        "Return only valid JSON matching the schema. Use null or empty arrays when data is missing. "
        "Do not invent facts. Summary must contain exactly 10 resume-supported bullets; the first bullet "
        "should summarize total professional experience if inferable.\n\n"
        f"Schema:\n{json.dumps(contract, indent=2)}\n\n"
        f"Resume text:\n{resume_text[:MAX_MODEL_INPUT_CHARS]}"
    )


def _extract_response_text(payload: dict[str, Any]) -> str:
    candidates = payload["candidates"]
    parts = candidates[0]["content"]["parts"]
    for part in parts:
        text = part.get("text")
        if text:
            return str(text)
    raise ValueError("Gemini response did not include text")


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _normalize_resume_data(data: object) -> dict[str, Any]:
    resume = data if isinstance(data, dict) else {}
    normalized = {
        "personal_info": _dict(resume.get("personal_info")),
        "summary": _list(resume.get("summary")),
        "experience": _list(resume.get("experience")),
        "education": _list(resume.get("education")),
        "skills": _list(resume.get("skills")),
        "awards": _list(resume.get("awards")),
        "projects": _list(resume.get("projects")),
        "additional_info": _dict(resume.get("additional_info")),
    }
    personal = normalized["personal_info"]
    normalized["personal_info"] = {
        "name": str(personal.get("name") or ""),
        "email": personal.get("email"),
        "phone": personal.get("phone"),
        "linkedin": personal.get("linkedin"),
        "portfolio_url": personal.get("portfolio_url"),
    }
    additional = normalized["additional_info"]
    normalized["additional_info"] = {
        "areas_of_expertise": _list(additional.get("areas_of_expertise")),
        "business_overview": str(additional.get("business_overview") or ""),
    }
    return normalized


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []
