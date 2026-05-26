from __future__ import annotations

from app.models.recruitment import JobRequisitionRules
from app.modules.ai_scoring.schema import ExtractedResumeFacts, ScoreResult
from app.shared.skill_aliases import matches_any_keyword, normalize_keyword, normalize_skill_text
from app.shared.skill_aliases import resolve_skill_anchor as resolve_skill_anchor_from_shared

FULL_SCORE_POINTS = 100
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


def score_resume_facts(
    rules: JobRequisitionRules,
    facts: ExtractedResumeFacts,
    *,
    is_flagged_for_cheating: bool = False,
) -> ScoreResult:
    knockout_rules = rules.knockoutRules or {}
    scoring_weights = rules.scoringWeights or {}
    failed_knockouts = _evaluate_knockouts(rules, facts)

    max_experience_points = int(scoring_weights.get("maxExperiencePoints") or 0)
    skill_weights = {
        normalize_keyword(str(skill)): int(points)
        for skill, points in (scoring_weights.get("skillWeights") or {}).items()
    }
    max_skill_points = int(scoring_weights.get("maxSkillPoints") or sum(skill_weights.values()))
    education_points = int(scoring_weights.get("educationPoints") or 0)
    certification_weights = {
        normalize_keyword(str(certification)): int(points)
        for certification, points in (scoring_weights.get("certificationWeights") or {}).items()
    }
    max_score = max(
        int(
            scoring_weights.get("totalPossiblePoints")
            or max_experience_points
            + max_skill_points
            + education_points
            + sum(certification_weights.values())
        ),
        FULL_SCORE_POINTS,
    )

    _backfill_normalized_skills(facts, skill_weights)

    if failed_knockouts:
        return ScoreResult(
            composite_score=0,
            raw_score=0,
            max_score=max_score,
            evaluation_status="REJECTED",
            failed_knockouts=failed_knockouts,
            score_breakdown={
                "rulesVersion": rules.rulesVersion,
                "knockoutFailed": True,
                "failedKnockouts": failed_knockouts,
                "experience": _experience_breakdown(facts, scoring_weights, 0),
                "skills": _skills_breakdown(facts, skill_weights, 0),
                "confidence": facts.overallConfidence,
                "targetRoleAlignment": facts.targetRoleAlignment.model_dump(),
                "explicitKnockoutAssessment": (
                    facts.explicitKnockoutAssessment.model_dump()
                    if facts.explicitKnockoutAssessment is not None
                    else None
                ),
            },
        )

    experience_score = _score_experience(facts, scoring_weights)
    matched_skills, skill_score = _score_skills(facts, skill_weights)
    education_score = _score_education(facts, scoring_weights, education_points)
    matched_certifications, certification_score = _score_certifications(
        facts,
        certification_weights,
    )
    raw_score = min(
        experience_score + skill_score + education_score + certification_score,
        max_score,
    )
    composite_score = round((raw_score / max_score) * 100) if max_score > 0 else 0

    explicit_rule = _normalize_explicit_knockout_rule(knockout_rules.get("explicitRule"))
    missing_knockout_assessment = bool(explicit_rule) and facts.explicitKnockoutAssessment is None
    role_mismatch = not facts.targetRoleAlignment.matchesTargetRole
    needs_manual_review = (
        is_flagged_for_cheating
        or not skill_weights
        or missing_knockout_assessment
        or role_mismatch
    )
    return ScoreResult(
        composite_score=composite_score,
        raw_score=raw_score,
        max_score=max_score,
        evaluation_status="NEEDS_REVIEW" if needs_manual_review else "QUALIFIED",
        failed_knockouts=[],
        score_breakdown={
            "rulesVersion": rules.rulesVersion,
            "knockoutFailed": False,
            "experience": _experience_breakdown(facts, scoring_weights, experience_score),
            "skills": _skills_breakdown(facts, skill_weights, skill_score),
            "education": {
                "awarded": education_score,
                "max": education_points,
                "evidence": facts.degree.model_dump() if facts.degree is not None else None,
            },
            "certifications": {
                "awarded": certification_score,
                "matched": matched_certifications,
                "max": sum(certification_weights.values()),
            },
            "rawScore": raw_score,
            "maxScore": max_score,
            "compositeScore": composite_score,
            "confidence": facts.overallConfidence,
            "targetRoleAlignment": facts.targetRoleAlignment.model_dump(),
            "explicitKnockoutRule": explicit_rule or None,
            "explicitKnockoutAssessment": (
                facts.explicitKnockoutAssessment.model_dump()
                if facts.explicitKnockoutAssessment is not None
                else None
            ),
            "requiresManualReview": needs_manual_review,
            "reviewReasons": (
                (["Suspicious hidden resume text found"] if is_flagged_for_cheating else [])
                + (["No weighted skill anchors configured for this requisition"] if not skill_weights else [])
                + (["Explicit knockout rule could not be assessed"] if missing_knockout_assessment else [])
                + (["Resume does not clearly align with the target role"] if role_mismatch else [])
            ),
            "matchedSkills": matched_skills,
            "missedSkills": sorted(set(skill_weights) - {item["normalizedSkill"] for item in matched_skills}),
        },
    )


def _evaluate_knockouts(rules: JobRequisitionRules, facts: ExtractedResumeFacts) -> list[dict]:
    knockout_rules = rules.knockoutRules or {}
    failures: list[dict] = []
    explicit_rule = _normalize_explicit_knockout_rule(knockout_rules.get("explicitRule"))
    assessment = facts.explicitKnockoutAssessment
    if explicit_rule and assessment is not None and not assessment.passed:
        failures.append(
            {
                "type": "explicitKnockoutRule",
                "required": explicit_rule,
                "found": "Candidate failed the explicit knockout rule",
                "evidence": assessment.evidence,
                "confidence": assessment.confidence,
            }
        )

    return failures


def _score_experience(facts: ExtractedResumeFacts, scoring_weights: dict) -> int:
    if facts.yearsExperience is None:
        return 0
    points_per_year = int(scoring_weights.get("experiencePointsPerYear") or 0)
    max_points = int(scoring_weights.get("maxExperiencePoints") or 0)
    return min(round(facts.yearsExperience.value * points_per_year), max_points)


def _score_skills(
    facts: ExtractedResumeFacts,
    skill_weights: dict[str, int],
) -> tuple[list[dict], int]:
    matched: list[dict] = []
    seen: set[str] = set()
    total = 0
    for skill in facts.skills:
        normalized_skill = resolve_skill_anchor_from_shared(
            skill.skill, skill.evidence, skill.normalizedSkill, skill_weights
        )
        if not normalized_skill:
            continue
        if normalized_skill in seen:
            continue
        seen.add(normalized_skill)
        points = skill_weights[normalized_skill]
        total += points
        matched.append(
            {
                "skill": skill.skill,
                "normalizedSkill": normalized_skill,
                "evidence": skill.evidence,
                "confidence": skill.confidence,
                "points": points,
            }
        )
    return matched, total


def _score_education(
    facts: ExtractedResumeFacts,
    scoring_weights: dict,
    education_points: int,
) -> int:
    if education_points <= 0 or facts.degree is None:
        return 0
    keywords = [normalize_keyword(item) for item in scoring_weights.get("educationKeywords") or []]
    if not keywords:
        return 0
    return education_points if _education_matches_keywords(facts.degree.value, keywords) else 0


def _score_certifications(
    facts: ExtractedResumeFacts,
    certification_weights: dict[str, int],
) -> tuple[list[dict], int]:
    if not certification_weights:
        return [], 0
    matched: list[dict] = []
    seen: set[str] = set()
    total = 0
    for certification in facts.certifications:
        value = normalize_keyword(certification.value)
        for anchor, points in certification_weights.items():
            if anchor in seen or not matches_any_keyword(value, [anchor]):
                continue
            seen.add(anchor)
            total += points
            matched.append(
                {
                    "certification": certification.value,
                    "normalizedCertification": anchor,
                    "evidence": certification.evidence,
                    "confidence": certification.confidence,
                    "points": points,
                }
            )
    return matched, total


def _experience_breakdown(
    facts: ExtractedResumeFacts,
    scoring_weights: dict,
    awarded: int,
) -> dict:
    return {
        "awarded": awarded,
        "max": int(scoring_weights.get("maxExperiencePoints") or 0),
        "pointsPerYear": int(scoring_weights.get("experiencePointsPerYear") or 0),
        "years": facts.yearsExperience.value if facts.yearsExperience is not None else None,
        "evidence": facts.yearsExperience.evidence if facts.yearsExperience is not None else None,
        "confidence": facts.yearsExperience.confidence if facts.yearsExperience is not None else None,
    }


def _skills_breakdown(
    facts: ExtractedResumeFacts,
    skill_weights: dict[str, int],
    awarded: int,
) -> dict:
    matched, _score = _score_skills(facts, skill_weights)
    return {
        "awarded": awarded,
        "max": sum(skill_weights.values()),
        "matched": matched,
        "missed": sorted(set(skill_weights) - {item["normalizedSkill"] for item in matched}),
    }



def _normalize_explicit_knockout_rule(value: object) -> str:
    normalized = str(value or "").strip()
    if normalize_keyword(normalized) in _NO_KNOCKOUT_VALUES:
        return ""
    return normalized


def _education_matches_keywords(value: str, keywords: list[str]) -> bool:
    normalized = normalize_skill_text(value)
    if not normalized:
        return False
    if "bachelor" in keywords and "bachelor" not in normalized and "bachelors" not in normalized:
        return False
    if "master" in keywords and "master" not in normalized and "masters" not in normalized:
        return False
    field_keywords = [keyword for keyword in keywords if keyword not in {"bachelor", "master", "engineering"}]
    if field_keywords:
        return any(normalize_skill_text(keyword) in normalized for keyword in field_keywords)
    return any(normalize_skill_text(keyword) in normalized for keyword in keywords)


def _backfill_normalized_skills(facts: ExtractedResumeFacts, skill_weights: dict[str, int]) -> None:
    if not skill_weights:
        return
    for skill in facts.skills:
        if skill.normalizedSkill is not None:
            continue
        resolved = resolve_skill_anchor_from_shared(
            skill.skill, skill.evidence, skill.normalizedSkill, skill_weights
        )
        if resolved:
            skill.normalizedSkill = resolved
