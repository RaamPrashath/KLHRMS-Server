from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HiringTeamMemberInput(BaseModel):
    memberId: str = Field(min_length=1)
    role: str | None = Field(default=None, max_length=120)


class HiringTeamCreateRequest(BaseModel):
    jobPostingId: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    stageId: str | None = Field(default=None, min_length=1)
    members: list[HiringTeamMemberInput] = Field(default_factory=list)


class HiringTeamUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    isActive: bool | None = None


class HiringTeamMemberRead(BaseModel):
    id: str
    memberId: str
    name: str | None
    email: str | None
    role: str | None


class HiringTeamRead(BaseModel):
    id: str
    jobPostingId: str
    stageId: str | None = None
    name: str
    description: str | None
    isActive: bool
    memberCount: int
    members: list[HiringTeamMemberRead]
    createdAt: datetime
    updatedAt: datetime


class HiringTeamListResponse(BaseModel):
    items: list[HiringTeamRead]
    total: int


class HiringTeamMemberAddRequest(BaseModel):
    memberId: str = Field(min_length=1)
    role: str | None = Field(default=None, max_length=120)
