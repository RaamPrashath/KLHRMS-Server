from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

ENTRY_METHODS = {"CARD_SWIPE", "BIOMETRIC", "MANUAL", "QR_CODE", "KEYPAD"}
ACCESS_STATUSES = {"GRANTED", "DENIED", "EXPIRED"}
ACCESS_DIRECTIONS = {"IN", "OUT"}
ASSIGNMENT_STATUSES = {"ACTIVE", "DISABLED"}


class AccessControlLogCreate(BaseModel):
    employeeMemberId: str = Field(min_length=1)
    assetId: str | None = None
    accessPoint: str = Field(min_length=1, max_length=120)
    entryMethod: str = Field(min_length=1, max_length=40)
    status: str = Field(min_length=1, max_length=20)
    direction: str = Field(min_length=1, max_length=10)
    enteredAt: datetime
    isActive: bool = True
    notes: str | None = None


class AccessControlLogUpdate(BaseModel):
    isActive: bool | None = None
    notes: str | None = None


class AccessControlLogResponse(BaseModel):
    id: str
    employeeMemberId: str
    assetId: str | None
    accessPoint: str
    entryMethod: str
    status: str
    direction: str
    enteredAt: datetime
    isActive: bool
    notes: str | None
    createdAt: datetime
    employeeName: str | None = None
    employeeEmail: str | None = None
    assetName: str | None = None
    assetCode: str | None = None


class AccessControlLogListResponse(BaseModel):
    items: list[AccessControlLogResponse]
    total: int
    page: int
    pageSize: int


class AccessControlAssignmentCreate(BaseModel):
    employeeMemberId: str = Field(min_length=1)
    accessPoint: str = Field(min_length=1, max_length=120)
    status: str = "ACTIVE"


class AccessControlAssignmentUpdate(BaseModel):
    status: str | None = None
    revokedAt: datetime | None = None


class AccessControlAssignmentResponse(BaseModel):
    id: str
    employeeMemberId: str
    accessPoint: str
    status: str
    grantedByMemberId: str | None
    grantedAt: datetime
    revokedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime
    employeeName: str | None = None
    employeeEmail: str | None = None
    grantedByName: str | None = None


class AccessControlAssignmentListResponse(BaseModel):
    items: list[AccessControlAssignmentResponse]
    total: int
    page: int
    pageSize: int


class AccessControlLogSummaryResponse(BaseModel):
    totalEntriesToday: int
    grantedToday: int
    deniedToday: int
    activeAssignments: int
    uniqueEmployeesToday: int
