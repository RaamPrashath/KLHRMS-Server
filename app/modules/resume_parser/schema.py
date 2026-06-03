from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TemplateType = Literal["default", "ncs", "rsc"]


class ResumeParserFileRead(BaseModel):
    originalFilename: str
    jsonUrl: str | None = None
    docxUrl: str | None = None
    status: Literal["success", "failed"]
    messages: list[str]


class ResumeParserProcessResponse(BaseModel):
    processedFiles: list[ResumeParserFileRead]


class ResumeParserHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    uploaderName: str | None = None
    originalFilename: str
    status: Literal["success", "failed"]
    createdAt: datetime
    jsonUrl: str | None = None
    docxUrl: str | None = None
    messages: list[str]


class ResumeParserHistoryResponse(BaseModel):
    scope: Literal["self", "organization"]
    items: list[ResumeParserHistoryRead]
