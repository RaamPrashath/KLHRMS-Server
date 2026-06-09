from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from app.integrations.gemini import (
    describe_gemini_error,
    gemini_generate_content_url,
    gemini_model_candidates,
    should_try_next_gemini_model,
)
from app.models.recruitment import JobRequisitionRules
from app.modules.ai_scoring.schema import ExtractedResumeFacts
from app.shared.config import get_settings
from app.shared.skill_aliases import SKILL_ALIASES

MAX_MODEL_INPUT_CHARS = 30000
_NO_KNOCKOUT_VALUES = {
    "none",
    "no",
    "n/a",
    "na",
    "nil",
    "not applicable",
    "no knockout",
    "no knockout rule",
}


class ResumeFactExtractionError(RuntimeError):
    pass


async def extract_resume_facts_with_gemini(
    resume_text: str,
    rules: JobRequisitionRules,
) -> ExtractedResumeFacts:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ResumeFactExtractionError("GEMINI_API_KEY is not configured")

    prompt = _build_extraction_prompt(resume_text, rules)
    last_error: Exception | None = None
    attempted_models: list[str] = []
    model_candidates = gemini_model_candidates(
        settings.gemini_model,
        getattr(settings, "gemini_fallback_models", ""),
    )
    for delay_seconds in (0.0, 1.5, 3.0):
        if delay_seconds:
            await asyncio.sleep(delay_seconds)
        for model in model_candidates:
            if model not in attempted_models:
                attempted_models.append(model)
            try:
                return await _call_gemini_for_facts(
                    prompt=prompt,
                    api_key=settings.gemini_api_key,
                    model=model,
                )
            except (
                httpx.HTTPError,
                ValidationError,
                json.JSONDecodeError,
                KeyError,
                ValueError,
            ) as exc:
                last_error = exc
                if should_try_next_gemini_model(exc):
                    continue
                break

    raise ResumeFactExtractionError(
        "Resume fact extraction failed after 3 attempts "
        f"across models {', '.join(attempted_models)}: {describe_gemini_error(last_error)}"
    ) from last_error


async def _call_gemini_for_facts(
    prompt: str,
    api_key: str,
    model: str,
) -> ExtractedResumeFacts:
    url = gemini_generate_content_url(model)
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, params={"key": api_key}, json=payload)
        response.raise_for_status()
    text = _extract_response_text(response.json())
    data = json.loads(_strip_json_fence(text))
    return ExtractedResumeFacts.model_validate(data)


def _build_extraction_prompt(resume_text: str, rules: JobRequisitionRules) -> str:
    knockout_rules = rules.knockoutRules or {}
    scoring_weights = rules.scoringWeights or {}
    source_snapshot = rules.sourceSnapshot or {}
    skill_weights = scoring_weights.get("skillWeights") or {}
    skill_anchors = sorted(str(skill) for skill in skill_weights)
    explicit_knockout_rule = _normalize_explicit_knockout_rule(knockout_rules.get("explicitRule"))
    clipped_resume_text = resume_text[:MAX_MODEL_INPUT_CHARS]

    contract = {
        "candidateName": {"value": "string", "evidence": "string", "confidence": 0.0},
        "targetRoleAlignment": {
            "matchesTargetRole": True,
            "evidence": "why the resume does or does not align to the target role",
            "confidence": 0.0,
        },
        "explicitKnockoutAssessment": {
            "passed": True,
            "evidence": "evidence that the candidate passes or fails the recruiter-entered knockout rule",
            "confidence": 0.0,
        },
        "yearsExperience": {
            "value": 0,
            "evidence": "evidence of experience relevant to this target role only",
            "confidence": 0.0,
        },
        "skills": [
            {
                "skill": "resume phrase",
                "normalizedSkill": "best-matching required skill anchor (lenient match), or null if none related",
                "evidence": "short resume quote or paraphrased evidence",
                "confidence": 0.0,
            }
        ],
        "degree": {"value": "string", "evidence": "string", "confidence": 0.0},
        "certifications": [{"value": "string", "evidence": "string", "confidence": 0.0}],
        "recommendationSummary": "plain-language hiring recommendation based only on resume evidence and job requirements",
        "professionalExperience": [
            {
                "title": "role, company, and dates when available",
                "bullets": ["simple resume-supported responsibility or impact"],
            }
        ],
        "projects": [
            {
                "title": "project name or concise project label",
                "bullets": ["simple resume-supported project detail"],
            }
        ],
        "achievements": ["simple resume-supported achievement"],
        "educationDetails": [
            {
                "title": "degree, institution, and dates when available",
                "bullets": ["simple resume-supported education detail"],
            }
        ],
        "certificationDetails": ["simple resume-supported certification detail"],
        "additionalSections": [
            {
                "title": "other resume section name",
                "bullets": ["simple resume-supported detail"],
            }
        ],
        "warnings": ["string"],
        "overallConfidence": 0.0,
    }

    return (
        "You normalize a sanitized resume into structured facts for an ATS scorer. "
        "Return only valid JSON matching this schema. Use null for optional objects when no "
        "evidence exists. Do not infer facts without resume evidence.\n\n"
        f"Schema:\n{json.dumps(contract, indent=2)}\n\n"
        f"Job title: {source_snapshot.get('title') or 'Unknown'}\n"
        f"Role requirements: {source_snapshot.get('requirements') or source_snapshot.get('requirementsRich') or 'Not provided'}\n"
        f"Required skill anchors: {json.dumps(skill_anchors)}\n"
        f"Skill mapping hints (resume phrase → anchor):\n"
        f"{json.dumps({k: list(v) for k, v in SKILL_ALIASES.items() if k in skill_anchors}, indent=2)}\n"
        f"Explicit knockout rule: {explicit_knockout_rule or 'None configured'}\n\n"
        "Rules:\n"
        "- targetRoleAlignment is required. Set matchesTargetRole false when the resume is clearly for another profession or has no evidence relevant to the target role.\n"
        "- explicitKnockoutAssessment must be null when no explicit knockout rule is configured.\n"
        "- If an explicit knockout rule is configured, evaluate only that rule and include evidence for pass or failure.\n"
        "- Do not treat job title, education, experience, skills, or certifications as knockout criteria unless they are stated in the explicit knockout rule.\n"
        "- yearsExperience must count only work relevant to the target job, not total experience in unrelated roles.\n"
        "- normalizedSkill: pick the best-matching required skill anchor using lenient/approximate matching. "
        "For example: 'Java/J2EE' or 'full stack java' maps to 'java'; "
        "'RESTful APIs' or 'REST' maps to 'rest api'; "
        "'Spring Boot' or 'Spring Framework' maps to 'spring'; "
        "'Jakarta Persistence' or 'JPA' maps to 'hibernate'. "
        "Only set null when NO required anchor is remotely related.\n"
        "- When Required skill anchors is empty, set normalizedSkill to null for observed skills; do not fail extraction.\n"
        "- Only include skills, education, and certifications supported by resume evidence.\n"
        "- Build professionalExperience, projects, achievements, educationDetails, certificationDetails, and additionalSections from resume text only.\n"
        "- For resume profile sections, preserve meaning but rewrite into simple, understandable bullet points. Do not add facts, employers, dates, projects, achievements, education, or certifications that are not present in the resume.\n"
        "- Omit empty resume profile sections by returning empty arrays.\n"
        "- recommendationSummary must summarize the AI's hiring recommendation for this specific job in one short paragraph. Mention key strengths and important gaps without inventing details.\n"
        "- Keep evidence concise and traceable to the resume text.\n"
        "- Confidence must be a number between 0 and 1.\n\n"
        f"Sanitized resume text:\n{clipped_resume_text}"
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


def _normalize_explicit_knockout_rule(value: object) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if " ".join(normalized.lower().split()) in _NO_KNOCKOUT_VALUES:
        return None
    return normalized
