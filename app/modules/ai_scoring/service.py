from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import ip_address
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recruitment import CandidateResumeAnalysis
from app.modules.ai_scoring.extractor import detect_resume_file_type, extract_resume_text
from app.modules.ai_scoring.llm_extractor import extract_resume_facts_with_gemini
from app.modules.ai_scoring.repository import ResumeAnalysisRepository
from app.modules.ai_scoring.schema import (
    ANALYSIS_VERSION,
    MAX_RESUME_BYTES,
    CandidateResumeAnalysisRead,
    DownloadedResume,
)
from app.modules.ai_scoring.scorer import score_resume_facts
from app.shared.database import AsyncSessionLocal


async def create_pending_resume_analysis(
    db: AsyncSession,
    organization_id: str,
    application_id: str,
    resume_url: str | None,
) -> CandidateResumeAnalysis:
    repository = ResumeAnalysisRepository(db)
    return await repository.upsert_pending_analysis(
        organization_id=organization_id,
        application_id=application_id,
        resume_url=resume_url,
    )


async def get_resume_analysis(
    db: AsyncSession,
    organization_id: str,
    application_id: str,
) -> CandidateResumeAnalysisRead:
    repository = ResumeAnalysisRepository(db)
    application = await repository.get_application(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Candidate application not found")
    analysis = await repository.get_analysis(organization_id, application_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Resume analysis not found")
    return _serialize_resume_analysis(analysis)


async def retry_resume_analysis(
    db: AsyncSession,
    organization_id: str,
    application_id: str,
    background_tasks: BackgroundTasks,
) -> CandidateResumeAnalysisRead:
    repository = ResumeAnalysisRepository(db)
    application = await repository.get_application(organization_id, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Candidate application not found")

    resume_url = application.candidate.resumeUrl if application.candidate is not None else None
    analysis = await repository.upsert_pending_analysis(organization_id, application_id, resume_url)
    analysis.status = "PENDING"
    analysis.lastError = None
    analysis.analysisVersion = ANALYSIS_VERSION
    await db.flush()
    await db.commit()
    await db.refresh(analysis)
    background_tasks.add_task(analyze_resume_for_application_task, organization_id, application_id)
    return _serialize_resume_analysis(analysis)


async def analyze_resume_for_application_task(
    organization_id: str,
    application_id: str,
) -> None:
    async with AsyncSessionLocal() as db:
        try:
            await analyze_resume_for_application(
                db=db,
                organization_id=organization_id,
                application_id=application_id,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            async with AsyncSessionLocal() as error_db:
                await _mark_analysis_failed(
                    error_db,
                    organization_id,
                    application_id,
                    "Resume analysis failed unexpectedly",
                )
                await error_db.commit()


async def analyze_resume_for_application(
    db: AsyncSession,
    organization_id: str,
    application_id: str,
) -> CandidateResumeAnalysis:
    repository = ResumeAnalysisRepository(db)
    application = await repository.get_application(organization_id, application_id)
    if application is None:
        raise ValueError("Candidate application not found")

    resume_url = application.candidate.resumeUrl if application.candidate is not None else None
    analysis = await repository.upsert_pending_analysis(organization_id, application_id, resume_url)
    analysis.status = "PROCESSING"
    analysis.attemptCount = (analysis.attemptCount or 0) + 1
    analysis.lastError = None
    analysis.analysisVersion = ANALYSIS_VERSION
    await db.flush()

    if not resume_url:
        analysis.status = "FAILED"
        analysis.lastError = "Resume URL is missing"
        return analysis

    try:
        downloaded = await download_resume(resume_url)
    except Exception as exc:
        analysis.status = "FAILED"
        analysis.lastError = str(exc)
        return analysis

    analysis.resumeUrl = downloaded.url
    analysis.resumeContentType = downloaded.content_type
    analysis.resumeFileType = downloaded.file_type
    analysis.resumeSizeBytes = len(downloaded.content)

    if downloaded.file_type == "unsupported":
        analysis.status = "UNSUPPORTED"
        analysis.lastError = "Resume file type is not supported"
        analysis.parserWarnings = [
            {
                "type": "unsupported_file_type",
                "message": "Only PDF, DOCX, and DOC resumes can be analyzed.",
            }
        ]
        return analysis

    try:
        extraction = extract_resume_text(downloaded.content, downloaded.file_type)
    except Exception as exc:
        analysis.status = "FAILED"
        analysis.lastError = str(exc)
        return analysis

    analysis.extractedText = extraction.extracted_text
    analysis.sanitizedText = extraction.sanitized_text
    analysis.firewallFlags = extraction.firewall_flags
    analysis.removedSuspiciousText = extraction.removed_suspicious_text
    analysis.parserWarnings = extraction.parser_warnings
    analysis.isFlaggedForCheating = bool(extraction.firewall_flags)
    analysis.status = "TEXT_EXTRACTED"
    analysis.evaluationStatus = "NEEDS_REVIEW" if extraction.firewall_flags else "TEXT_EXTRACTED"
    analysis.analyzedAt = datetime.now(UTC)

    rules = await repository.get_rules_for_application(organization_id, application_id)
    if rules is None:
        analysis.lastError = "AI screening rules are not available for this application"
        return analysis

    if not extraction.sanitized_text.strip():
        analysis.status = "FAILED"
        analysis.lastError = "Resume text extraction returned no usable text"
        return analysis

    try:
        facts = await extract_resume_facts_with_gemini(extraction.sanitized_text, rules)
        score = score_resume_facts(
            rules,
            facts,
            is_flagged_for_cheating=analysis.isFlaggedForCheating,
        )
    except Exception as exc:
        analysis.status = "FAILED"
        analysis.lastError = str(exc)
        analysis.analyzedAt = datetime.now(UTC)
        return analysis

    analysis.extractedFacts = {
        **facts.model_dump(mode="json"),
        "rulesVersion": rules.rulesVersion,
        "rulesId": rules.id,
        "explicitKnockoutRule": (rules.knockoutRules or {}).get("explicitRule"),
    }
    analysis.extractionConfidence = facts.overallConfidence
    analysis.compositeScore = score.composite_score
    analysis.rawScore = score.raw_score
    analysis.maxScore = score.max_score
    analysis.evaluationStatus = score.evaluation_status
    analysis.failedKnockouts = score.failed_knockouts
    analysis.scoreBreakdown = score.score_breakdown
    analysis.status = "COMPLETED"
    analysis.lastError = None
    analysis.analyzedAt = datetime.now(UTC)
    return analysis


async def download_resume(url: str) -> DownloadedResume:
    _validate_resume_url(url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        response = await client.get(url)
        response.raise_for_status()
    content = response.content
    if not content:
        raise RuntimeError("Resume download returned an empty file")
    if len(content) > MAX_RESUME_BYTES:
        raise RuntimeError("Resume file is larger than the 10 MB analysis limit")
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip() or None
    file_type = detect_resume_file_type(url, content_type, content)
    return DownloadedResume(
        url=url,
        content=content,
        content_type=content_type,
        file_type=file_type,
    )


def _validate_resume_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("Resume URL must be an HTTP or HTTPS URL")
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Resume URL host is not allowed")
    try:
        host_ip = ip_address(hostname)
    except ValueError:
        return
    if host_ip.is_private or host_ip.is_loopback or host_ip.is_link_local:
        raise RuntimeError("Resume URL host is not allowed")


async def _mark_analysis_failed(
    db: AsyncSession,
    organization_id: str,
    application_id: str,
    message: str,
) -> None:
    repository = ResumeAnalysisRepository(db)
    analysis = await repository.get_analysis(organization_id, application_id)
    if analysis is None:
        analysis = await repository.upsert_pending_analysis(organization_id, application_id, None)
    analysis.status = "FAILED"
    analysis.lastError = message
    analysis.attemptCount = (analysis.attemptCount or 0) + 1
    analysis.analysisVersion = ANALYSIS_VERSION
    analysis.analyzedAt = datetime.now(UTC)
    db.add(analysis)


def _serialize_resume_analysis(
    analysis: CandidateResumeAnalysis,
) -> CandidateResumeAnalysisRead:
    return CandidateResumeAnalysisRead.model_validate(analysis)
