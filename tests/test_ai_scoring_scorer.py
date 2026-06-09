from types import SimpleNamespace

import httpx
import pytest

from app.models.recruitment import EmploymentType, JobRequisition, JobRequisitionRules
from app.modules.ai_scoring import llm_extractor
from app.modules.ai_scoring.schema import (
    EvidenceFact,
    ExtractedResumeFacts,
    KnockoutAssessmentFact,
    RoleAlignmentFact,
    SkillEvidence,
    YearsExperienceFact,
)
from app.modules.ai_scoring.scorer import score_resume_facts
from app.modules.jobs.service import _compile_requisition_rules


def _rules() -> JobRequisitionRules:
    return JobRequisitionRules(
        id="rules-1",
        organizationId="org-1",
        requisitionId="req-1",
        rulesVersion="1.0",
        knockoutRules={"explicitRule": None},
        scoringWeights={
            "experiencePointsPerYear": 10,
            "maxExperiencePoints": 40,
            "maxSkillPoints": 60,
            "skillWeights": {"python": 30, "react": 30},
            "totalPossiblePoints": 100,
        },
        sourceSnapshot={"title": "Senior Java Developer"},
    )


def _facts(years: float = 5) -> ExtractedResumeFacts:
    return ExtractedResumeFacts(
        candidateName=EvidenceFact(value="Ada Lovelace", evidence="Ada Lovelace", confidence=0.9),
        targetRoleAlignment=RoleAlignmentFact(
            matchesTargetRole=True,
            evidence="Built server applications for comparable software roles",
            confidence=0.9,
        ),
        yearsExperience=YearsExperienceFact(
            value=years,
            evidence=f"{years} years building HR systems",
            confidence=0.86,
        ),
        skills=[
            SkillEvidence(
                skill="Python",
                normalizedSkill="python",
                evidence="Built APIs with Python",
                confidence=0.94,
            ),
            SkillEvidence(
                skill="React.js",
                normalizedSkill="react",
                evidence="Created dashboards in React",
                confidence=0.9,
            ),
        ],
        degree=EvidenceFact(
            value="Bachelor of Engineering",
            evidence="Bachelor of Engineering",
            confidence=0.88,
        ),
        certifications=[],
        warnings=[],
        overallConfidence=0.9,
    )


def test_score_resume_facts_is_deterministic_and_evidence_backed():
    first = score_resume_facts(_rules(), _facts())
    second = score_resume_facts(_rules(), _facts())

    assert first == second
    assert first.raw_score == 100
    assert first.composite_score == 100
    assert first.evaluation_status == "QUALIFIED"
    assert first.score_breakdown["skills"]["matched"][0]["evidence"] == "Built APIs with Python"


def test_extracted_resume_facts_accepts_profile_sections_without_affecting_score():
    facts = ExtractedResumeFacts.model_validate(
        {
            **_facts().model_dump(mode="json"),
            "recommendationSummary": (
                "Candidate has relevant backend experience and matches the core role requirements."
            ),
            "professionalExperience": [
                {
                    "title": "Software Engineer, Example Systems",
                    "bullets": ["Built APIs with Python", "Created dashboards in React"],
                }
            ],
            "projects": [
                {
                    "title": "HR dashboard",
                    "bullets": ["Built a dashboard for HR operations"],
                }
            ],
            "achievements": ["Improved reporting turnaround time"],
            "educationDetails": [
                {
                    "title": "Bachelor of Engineering",
                    "bullets": ["Completed engineering degree"],
                }
            ],
            "certificationDetails": ["Certified Python Developer"],
        }
    )

    result = score_resume_facts(_rules(), facts)

    assert facts.professionalExperience[0].title == "Software Engineer, Example Systems"
    assert result.composite_score == 100
    assert result.evaluation_status == "QUALIFIED"


def test_score_resume_facts_applies_hard_knockout_before_points():
    rules = _rules()
    rules.knockoutRules = {"explicitRule": "Candidate must have at least 3 years of Java experience."}
    facts = _facts(years=1)
    facts.explicitKnockoutAssessment = KnockoutAssessmentFact(
        passed=False,
        evidence="Only 1 year of relevant Java experience found.",
        confidence=0.98,
    )
    result = score_resume_facts(rules, facts)

    assert result.raw_score == 0
    assert result.composite_score == 0
    assert result.evaluation_status == "REJECTED"
    assert result.failed_knockouts[0]["type"] == "explicitKnockoutRule"


def test_firewall_flag_warns_without_auto_rejecting_qualified_candidate():
    result = score_resume_facts(
        _rules(),
        _facts(),
        is_flagged_for_cheating=True,
    )

    assert result.raw_score == 100
    assert result.evaluation_status == "NEEDS_REVIEW"
    assert result.failed_knockouts == []


def test_unrelated_target_role_requires_review_without_automatic_rejection():
    facts = _facts()
    facts.targetRoleAlignment = RoleAlignmentFact(
        matchesTargetRole=False,
        evidence="Resume is for a Graphic Designer, not a Senior Java Developer",
        confidence=1,
    )

    result = score_resume_facts(_rules(), facts)

    assert result.raw_score == 100
    assert result.composite_score == 100
    assert result.evaluation_status == "NEEDS_REVIEW"
    assert result.failed_knockouts == []


def test_experience_only_rules_require_review_instead_of_recommendation():
    rules = _rules()
    rules.scoringWeights = {
        "experiencePointsPerYear": 8,
        "maxExperiencePoints": 40,
        "maxSkillPoints": 0,
        "skillWeights": {},
        "totalPossiblePoints": 40,
    }

    result = score_resume_facts(rules, _facts())

    assert result.raw_score == 40
    assert result.max_score == 100
    assert result.composite_score == 40
    assert result.evaluation_status == "NEEDS_REVIEW"
    assert result.score_breakdown["requiresManualReview"] is True


def test_education_does_not_reject_candidate_without_explicit_knockout_rule():
    facts = _facts()
    facts.degree = None

    result = score_resume_facts(_rules(), facts)

    assert result.composite_score == 100
    assert result.evaluation_status == "QUALIFIED"
    assert result.failed_knockouts == []


def test_unmapped_skills_are_valid_but_award_no_points():
    facts = _facts()
    facts.skills = [
        SkillEvidence(
            skill="Adobe Illustrator",
            normalizedSkill=None,
            evidence="Created vector designs in Adobe Illustrator",
            confidence=0.9,
        )
    ]

    result = score_resume_facts(_rules(), facts)

    assert result.composite_score == 40
    assert result.score_breakdown["skills"]["awarded"] == 0


def test_scoring_falls_back_to_resume_skill_text_when_normalized_skill_is_null():
    rules = _rules()
    rules.scoringWeights = {
        "experiencePointsPerYear": 8,
        "maxExperiencePoints": 40,
        "maxSkillPoints": 60,
        "skillWeights": {"java": 20, "spring": 20, "rest api": 20},
        "totalPossiblePoints": 100,
    }
    facts = _facts()
    facts.skills = [
        SkillEvidence(
            skill="Java/J2EE Developer",
            normalizedSkill=None,
            evidence="10 years of experience as a Java/J2EE Developer",
            confidence=1,
        ),
        SkillEvidence(
            skill="Spring Framework",
            normalizedSkill=None,
            evidence="Industry Knowledge: Spring Framework",
            confidence=1,
        ),
        SkillEvidence(
            skill="Restful APIS",
            normalizedSkill=None,
            evidence="Frameworks (Advanced) Restful APIS",
            confidence=1,
        ),
    ]

    result = score_resume_facts(rules, facts)

    assert result.raw_score == 100
    assert {item["normalizedSkill"] for item in result.score_breakdown["skills"]["matched"]} == {
        "java",
        "spring",
        "rest api",
    }


def test_requisition_rules_derive_java_anchors_and_ignore_none_knockout_rule():
    requisition = JobRequisition(
        id="req-1",
        organizationId="org-1",
        title="Senior Java Developer",
        employmentType=EmploymentType.FULL_TIME,
        openings=1,
        raisedById="member-1",
        skills=["Senior"],
        minExperience=5,
        education="Bachelor's degree in Computer Science and Engineering",
        knockoutRule="none",
        requirementsRich=(
            "5+ years of experience in Java development. Strong knowledge of Java, "
            "Spring Boot, Hibernate, and REST APIs. Experience with microservices, "
            "PostgreSQL, MongoDB, Git, Docker, and CI/CD tools."
        ),
    )

    rules = _compile_requisition_rules(requisition, job_posting_id=None)

    assert rules.knockoutRules == {"explicitRule": None}
    assert "senior" not in rules.scoringWeights["skillWeights"]
    assert {"java", "spring", "hibernate", "rest api"}.issubset(
        set(rules.scoringWeights["skillWeights"])
    )
    assert rules.scoringWeights["educationPoints"] == 10
    assert rules.scoringWeights["totalPossiblePoints"] == 100


@pytest.mark.asyncio
async def test_gemini_extraction_retries_until_valid_structured_facts(monkeypatch):
    calls = 0

    async def fake_call_gemini_for_facts(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("invalid structured output")
        return _facts()

    async def fake_sleep(_delay_seconds):
        return None

    monkeypatch.setattr(
        llm_extractor,
        "get_settings",
        lambda: SimpleNamespace(gemini_api_key="test-key", gemini_model="test-model"),
    )
    monkeypatch.setattr(llm_extractor, "_call_gemini_for_facts", fake_call_gemini_for_facts)
    monkeypatch.setattr(llm_extractor.asyncio, "sleep", fake_sleep)

    facts = await llm_extractor.extract_resume_facts_with_gemini("resume text", _rules())

    assert calls == 3
    assert facts.overallConfidence == 0.9


@pytest.mark.asyncio
async def test_gemini_extraction_falls_back_to_next_model_on_503(monkeypatch):
    attempted_models: list[str] = []

    async def fake_call_gemini_for_facts(*args, **kwargs):
        model = kwargs["model"]
        attempted_models.append(model)
        if model == "gemini-2.5-flash":
            request = httpx.Request(
                "POST",
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=secret",
            )
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("server unavailable", request=request, response=response)
        return _facts()

    monkeypatch.setattr(
        llm_extractor,
        "get_settings",
        lambda: SimpleNamespace(
            gemini_api_key="test-key",
            gemini_model="gemini-2.5-flash",
            gemini_fallback_models="gemini-3.5-flash",
        ),
    )
    monkeypatch.setattr(llm_extractor, "_call_gemini_for_facts", fake_call_gemini_for_facts)

    facts = await llm_extractor.extract_resume_facts_with_gemini("resume text", _rules())

    assert attempted_models == ["gemini-2.5-flash", "gemini-3.5-flash"]
    assert facts.overallConfidence == 0.9
