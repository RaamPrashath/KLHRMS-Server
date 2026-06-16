from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AllowedOfferTemplateStatus = Literal["DRAFT", "ACTIVE", "ARCHIVED"]
AllowedOfferBatchStatus = Literal["QUEUED", "PROCESSING", "COMPLETED", "PARTIAL_FAILED", "FAILED"]
AllowedOfferLetterStatus = Literal[
    "DRAFT",
    "SENT",
    "FAILED",
    "ACCEPTED",
    "REJECTED",
    "EXPIRED",
    "WITHDRAWN",
]
AllowedOfferDownloadFormat = Literal["pdf", "docx"]

ALLOWED_VARIABLE_TOKENS = {
    "candidate.firstName",
    "candidate.lastName",
    "offer.generatedDate",
    "job.salaryMin",
    "job.salaryMax",
    "job.currency",
}
COMPENSATION_VARIABLE_TOKENS = {"job.salaryMin", "job.salaryMax", "job.currency"}
VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)*)\s*\}\}")


def validate_offer_asset_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    normalized = stripped.replace("\\", "/").lower()
    if "/uploads/offers/" in normalized or normalized.startswith("uploads/offers/"):
        raise ValueError("Offer assets must be uploaded to the Supabase offer-letter bucket")
    return stripped


class _OfferHtmlSanitizer(HTMLParser):
    allowed_tags = {
        "a",
        "b",
        "blockquote",
        "br",
        "div",
        "em",
        "h1",
        "h2",
        "h3",
        "hr",
        "li",
        "ol",
        "p",
        "span",
        "strong",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "u",
        "ul",
    }
    allowed_attrs = {"href", "colspan", "rowspan"}
    skip_content_tags = {"script", "style"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.skip_content_tags:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in self.allowed_tags:
            return
        safe_attrs = []
        for name, value in attrs:
            if name not in self.allowed_attrs or value is None:
                continue
            escaped = self._escape(value.strip(), quote=True)
            if name == "href" and escaped.lower().startswith(("javascript:", "data:")):
                continue
            safe_attrs.append(f'{name}="{escaped}"')
        suffix = f" {' '.join(safe_attrs)}" if safe_attrs else ""
        self.parts.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.skip_content_tags and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth or tag not in self.allowed_tags or tag in {"br", "hr"}:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(self._escape(data, quote=False))

    @staticmethod
    def _escape(value: str, *, quote: bool) -> str:
        escaped = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return escaped.replace('"', "&quot;") if quote else escaped


def sanitize_offer_html(value: str | None) -> str | None:
    if value is None:
        return None
    parser = _OfferHtmlSanitizer()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts)


def validate_offer_variables(value: str | None) -> str | None:
    if value is None:
        return None
    unknown_tokens = sorted(
        {match.group(1) for match in VARIABLE_PATTERN.finditer(value)}
        - ALLOWED_VARIABLE_TOKENS
    )
    if unknown_tokens:
        raise ValueError(f"Unknown offer variable token(s): {', '.join(unknown_tokens)}")
    return value


class OfferTemplateCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    templateId: str
    name: str
    slug: str
    order: int
    createdAt: datetime
    updatedAt: datetime


class OfferTemplateCategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    slug: str | None = Field(default=None, max_length=100)
    order: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Category name is required")
        return stripped


class OfferTemplateSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    templateId: str
    categoryId: str
    sectionKey: str
    sectionName: str
    order: int
    tiptapJson: dict[str, Any]
    html: str
    createdAt: datetime
    updatedAt: datetime


class OfferTemplateSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    name: str
    description: str | None = None
    status: str
    logoUrl: str | None = None
    signatureUrl: str | None = None
    signatoryName: str | None = None
    signatoryTitle: str | None = None
    lastUsedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class OfferTemplateRead(OfferTemplateSummaryRead):
    footerHtml: str | None = None
    websiteUrl: str | None = None
    createdByMemberId: str | None = None
    updatedByMemberId: str | None = None
    categories: list[OfferTemplateCategoryRead] = Field(default_factory=list)
    sections: list[OfferTemplateSectionRead] = Field(default_factory=list)


class OfferTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: AllowedOfferTemplateStatus = "DRAFT"
    logoUrl: str | None = Field(default=None, max_length=4096)
    signatureUrl: str | None = Field(default=None, max_length=4096)
    signatoryName: str | None = Field(default=None, max_length=160)
    signatoryTitle: str | None = Field(default=None, max_length=160)
    footerHtml: str | None = None
    websiteUrl: str | None = None
    categories: list[OfferTemplateCategoryInput] = Field(default_factory=list)

    @field_validator("name", "signatoryName", "signatoryTitle")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field is required")
        return stripped

    @field_validator("footerHtml")
    @classmethod
    def sanitize_footer_html(cls, value: str | None) -> str | None:
        return validate_offer_variables(sanitize_offer_html(value))

    @field_validator("logoUrl", "signatureUrl")
    @classmethod
    def validate_asset_url(cls, value: str | None) -> str | None:
        return validate_offer_asset_url(value)


class OfferTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: AllowedOfferTemplateStatus | None = None
    logoUrl: str | None = Field(default=None, max_length=4096)
    signatureUrl: str | None = Field(default=None, max_length=4096)
    signatoryName: str | None = Field(default=None, max_length=160)
    signatoryTitle: str | None = Field(default=None, max_length=160)
    footerHtml: str | None = None
    websiteUrl: str | None = None

    @field_validator("name", "signatoryName", "signatoryTitle")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field is required")
        return stripped

    @field_validator("footerHtml")
    @classmethod
    def sanitize_footer_html(cls, value: str | None) -> str | None:
        return validate_offer_variables(sanitize_offer_html(value))

    @field_validator("logoUrl", "signatureUrl")
    @classmethod
    def validate_asset_url(cls, value: str | None) -> str | None:
        return validate_offer_asset_url(value)


class OfferTemplateCopyRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


class OfferTemplateCategoryCreateRequest(OfferTemplateCategoryInput):
    pass


class OfferTemplateSectionUpsertRequest(BaseModel):
    sectionKey: str | None = Field(default=None, min_length=1, max_length=80)
    sectionName: str = Field(min_length=1, max_length=120)
    order: int = Field(ge=1)
    tiptapJson: dict[str, Any] = Field(default_factory=dict)
    html: str = ""

    @model_validator(mode="after")
    def sanitize_and_validate_html(self) -> "OfferTemplateSectionUpsertRequest":
        sanitized = sanitize_offer_html(self.html) or ""
        self.html = validate_offer_variables(sanitized) or ""
        return self


class OfferLetterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    applicationId: str
    batchId: str | None = None
    templateId: str | None = None
    templateCategoryId: str | None = None
    stageId: str | None = None
    status: str
    title: str
    message: str | None = None
    salary: float | None = None
    currency: str
    joiningDate: datetime | None = None
    expiresAt: datetime | None = None
    sentAt: datetime | None = None
    respondedAt: datetime | None = None
    candidateToken: str | None = None
    pdfUrl: str | None = None
    renderedHtml: str | None = None
    storageBucket: str | None = None
    storagePath: str | None = None
    fileName: str | None = None
    emailSentAt: datetime | None = None
    emailError: str | None = None
    responseIgnoredAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime


class OfferDispatchBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    jobPostingId: str
    stageId: str | None = None
    templateId: str | None = None
    templateCategoryId: str | None = None
    status: str
    candidateCount: int
    successCount: int
    failureCount: int
    createdByMemberId: str | None = None
    createdAt: datetime
    completedAt: datetime | None = None
    errorSummary: str | None = None


class OfferStageSummaryRead(BaseModel):
    id: str
    name: str
    slug: str
    stageType: str
    order: float


class OfferJobPostingSummaryRead(BaseModel):
    id: str
    slug: str
    title: str
    requisitionId: str | None = None


class OfferCandidateSummaryRead(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: str | None = None
    resumeUrl: str | None = None


class OfferEligibilityRead(BaseModel):
    canSend: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OfferWorkspaceCandidateRead(BaseModel):
    applicationId: str
    candidate: OfferCandidateSummaryRead
    appliedAt: datetime
    source: str
    offerStatus: str
    latestOffer: OfferLetterRead | None = None
    eligibility: OfferEligibilityRead


class OfferTemplateListItemRead(OfferTemplateSummaryRead):
    categoryNames: list[str] = Field(default_factory=list)


class OfferStageWorkspaceRead(BaseModel):
    stage: OfferStageSummaryRead
    jobPosting: OfferJobPostingSummaryRead
    candidateCount: int
    candidates: list[OfferWorkspaceCandidateRead] = Field(default_factory=list)
    templates: list[OfferTemplateListItemRead] = Field(default_factory=list)
    recentTemplate: OfferTemplateListItemRead | None = None
    latestBatch: OfferDispatchBatchRead | None = None
    acceptedStage: OfferStageSummaryRead | None = None
    rejectedStage: OfferStageSummaryRead | None = None
    jobHasSalaryData: bool = False


class OfferCandidateValidationRequest(BaseModel):
    templateId: str = Field(min_length=1)
    categoryId: str = Field(min_length=1)
    applicationIds: list[str] = Field(min_length=1)
    expiresAt: datetime | None = None


class OfferDispatchCreateRequest(OfferCandidateValidationRequest):
    pass


class OfferDownloadCreateRequest(OfferCandidateValidationRequest):
    format: AllowedOfferDownloadFormat


class OfferCandidateValidationResultRead(BaseModel):
    applicationId: str
    candidate: OfferCandidateSummaryRead | None = None
    eligibility: OfferEligibilityRead


class OfferCandidateValidationResponse(BaseModel):
    validCandidates: list[OfferCandidateValidationResultRead] = Field(default_factory=list)
    blockedCandidates: list[OfferCandidateValidationResultRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OfferDispatchCreateResponse(BaseModel):
    batch: OfferDispatchBatchRead | None = None
    queuedOfferLetters: list[OfferLetterRead] = Field(default_factory=list)
    blockedCandidates: list[OfferCandidateValidationResultRead] = Field(default_factory=list)


class OfferDispatchBatchDetailRead(BaseModel):
    batch: OfferDispatchBatchRead
    offerLetters: list[OfferLetterRead] = Field(default_factory=list)


class OfferApplicationLettersRead(BaseModel):
    applicationId: str
    offerLetters: list[OfferLetterRead] = Field(default_factory=list)
