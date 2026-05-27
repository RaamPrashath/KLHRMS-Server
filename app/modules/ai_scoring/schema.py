from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ANALYSIS_VERSION = "0.7"
MAX_RESUME_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class DownloadedResume:
    url: str
    content: bytes
    content_type: str | None
    file_type: str


@dataclass(frozen=True)
class TextExtractionResult:
    extracted_text: str
    sanitized_text: str
    firewall_flags: list[dict] = field(default_factory=list)
    removed_suspicious_text: list[dict] = field(default_factory=list)
    parser_warnings: list[dict] = field(default_factory=list)


class EvidenceFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class SkillEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    normalizedSkill: str | None = None
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class YearsExperienceFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(ge=0)
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class RoleAlignmentFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matchesTargetRole: bool
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class KnockoutAssessmentFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class ResumeProfileSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    bullets: list[str] = Field(default_factory=list)


class ExtractedResumeFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidateName: EvidenceFact | None = None
    targetRoleAlignment: RoleAlignmentFact
    explicitKnockoutAssessment: KnockoutAssessmentFact | None = None
    yearsExperience: YearsExperienceFact | None = None
    skills: list[SkillEvidence] = Field(default_factory=list)
    degree: EvidenceFact | None = None
    certifications: list[EvidenceFact] = Field(default_factory=list)
    recommendationSummary: str | None = None
    professionalExperience: list[ResumeProfileSection] = Field(default_factory=list)
    projects: list[ResumeProfileSection] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    educationDetails: list[ResumeProfileSection] = Field(default_factory=list)
    certificationDetails: list[str] = Field(default_factory=list)
    additionalSections: list[ResumeProfileSection] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    overallConfidence: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class ScoreResult:
    composite_score: int
    raw_score: int
    max_score: int
    evaluation_status: Literal["QUALIFIED", "REJECTED", "NEEDS_REVIEW"]
    failed_knockouts: list[dict]
    score_breakdown: dict


class CandidateResumeAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    applicationId: str
    status: str
    resumeUrl: str | None = None
    resumeContentType: str | None = None
    resumeFileType: str | None = None
    resumeSizeBytes: int | None = None
    firewallFlags: list[dict] | None = None
    removedSuspiciousText: list[dict] | None = None
    isFlaggedForCheating: bool
    parserWarnings: list[dict] | None = None
    extractedFacts: dict | None = None
    compositeScore: int | None = None
    rawScore: int | None = None
    maxScore: int | None = None
    evaluationStatus: str | None = None
    failedKnockouts: list[dict] | None = None
    scoreBreakdown: dict | None = None
    extractionConfidence: float | None = None
    analysisVersion: str
    attemptCount: int
    lastError: str | None = None
    analyzedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime
