from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TemplateStatus = Literal["DRAFT", "ACTIVE", "ARCHIVED"]
FieldType = Literal["FILE_UPLOAD", "SHORT_TEXT", "LONG_TEXT", "DATE"]
AllowedFormatGroup = Literal["IMAGE", "FILE", "VIDEO", "ALL"]
RequestStatus = Literal["PENDING", "SUBMITTED", "FAILED"]


class DocumentCollectionFieldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    templateId: str
    fieldType: str
    name: str
    description: str | None = None
    required: bool
    order: int
    allowedFormatGroup: str
    maxSizeBytes: int | None = None
    createdAt: datetime
    updatedAt: datetime


class DocumentCollectionFieldInput(BaseModel):
    id: str | None = None
    fieldType: FieldType = "FILE_UPLOAD"
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    required: bool = True
    order: int | None = Field(default=None, ge=1)
    allowedFormatGroup: AllowedFormatGroup = "ALL"
    maxSizeBytes: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field name is required")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def normalize_non_file_config(self) -> DocumentCollectionFieldInput:
        if self.fieldType != "FILE_UPLOAD":
            self.allowedFormatGroup = "ALL"
            self.maxSizeBytes = None
        return self


class DocumentCollectionTemplateListItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    name: str
    description: str | None = None
    status: str
    lastUsedAt: datetime | None = None
    createdAt: datetime
    updatedAt: datetime
    fieldCount: int = 0


class DocumentCollectionTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organizationId: str
    name: str
    description: str | None = None
    status: str
    lastUsedAt: datetime | None = None
    createdByMemberId: str | None = None
    updatedByMemberId: str | None = None
    createdAt: datetime
    updatedAt: datetime
    fields: list[DocumentCollectionFieldRead] = Field(default_factory=list)


class DocumentCollectionTemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    status: TemplateStatus = "DRAFT"
    fields: list[DocumentCollectionFieldInput] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Template name is required")
        return stripped


class DocumentCollectionTemplateUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    status: TemplateStatus | None = None
    fields: list[DocumentCollectionFieldInput] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Template name is required")
        return stripped


class DocumentCollectionTemplateCopyRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)


class DocumentCollectionSendRequest(BaseModel):
    templateId: str = Field(min_length=1)
    applicationIds: list[str] = Field(min_length=1)


class DocumentCollectionSendResponse(BaseModel):
    requestedCount: int


class DocumentCollectionRequestSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    templateId: str | None = None
    templateName: str
    status: str
    tokenSentAt: datetime | None = None
    submittedAt: datetime | None = None
    emailError: str | None = None
    createdAt: datetime


class DocumentCollectionRequestDetailRead(DocumentCollectionRequestSummaryRead):
    templateSnapshotJson: dict[str, Any]
    answersJson: dict[str, Any] | None = None


class DocumentCollectionCandidateSummaryRead(BaseModel):
    id: str
    firstName: str
    lastName: str
    email: str | None = None
    resumeUrl: str | None = None


class DocumentCollectionPublicRead(BaseModel):
    token: str
    candidateName: str
    jobTitle: str
    organizationName: str
    status: str
    submittedAt: datetime | None = None
    template: dict[str, Any]


class DocumentCollectionPublicAnswerInput(BaseModel):
    fieldId: str = Field(min_length=1)
    value: str | None = None
    fileBase64: str | None = None
    fileName: str | None = None
    fileType: str | None = None
    fileSize: int | None = Field(default=None, ge=0)


class DocumentCollectionSubmitRequest(BaseModel):
    answers: list[DocumentCollectionPublicAnswerInput] = Field(default_factory=list)


class DocumentCollectionSubmitResponse(BaseModel):
    status: str
    message: str
