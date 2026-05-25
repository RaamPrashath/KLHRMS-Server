"""Pydantic schemas for the leave module."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

LeaveRequestStatus = Literal["PENDING", "APPROVED", "REJECTED", "CANCELLED"]


class LeaveTypeBasePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    quota: float = Field(..., ge=0)
    carry_forward: bool = Field(default=False, alias="carryForward")
    is_paid: bool = Field(default=True, alias="isPaid")
    color: str | None = Field(default=None, max_length=20)

    model_config = {"populate_by_name": True}

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("name is required")
        return trimmed

    @field_validator("color")
    @classmethod
    def normalize_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class LeaveTypeCreateRequest(LeaveTypeBasePayload):
    pass


class LeaveTypeUpdateRequest(LeaveTypeBasePayload):
    pass


class HolidayBasePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    holiday_date: dt.date = Field(..., alias="holidayDate")
    is_recurring: bool = Field(default=False, alias="isRecurring")
    description: str | None = Field(default=None, max_length=2000)

    model_config = {"populate_by_name": True}

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("name is required")
        return trimmed

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if trimmed.lower() == "null":
            return None
        return trimmed or None


class HolidayCreateRequest(HolidayBasePayload):
    pass


class HolidayUpdateRequest(HolidayBasePayload):
    pass


class LeaveRequestCreateRequest(BaseModel):
    leave_type_id: str = Field(..., alias="leaveTypeId")
    member_id: str | None = Field(default=None, alias="memberId")
    start_date: dt.date = Field(..., alias="startDate")
    end_date: dt.date = Field(..., alias="endDate")
    days: float = Field(..., ge=0)
    reason: str | None = Field(default=None, max_length=2000)

    model_config = {"populate_by_name": True}

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="after")
    def validate_dates(self) -> LeaveRequestCreateRequest:
        if self.end_date < self.start_date:
            raise ValueError("endDate must be on or after startDate")
        return self


class LeaveRequestDecisionRequest(BaseModel):
    approver_comment: str | None = Field(default=None, alias="approverComment", max_length=2000)

    model_config = {"populate_by_name": True}

    @field_validator("approver_comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class LeaveRequestFilters(BaseModel):
    status: str | None = None
    member_id: str | None = Field(default=None, alias="memberId")
    leave_type_id: str | None = Field(default=None, alias="leaveTypeId")
    from_date: dt.date | None = Field(default=None, alias="fromDate")
    to_date: dt.date | None = Field(default=None, alias="toDate")
    year: int | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    model_config = {"populate_by_name": True}


class LeaveBalanceFilters(BaseModel):
    year: int | None = None
    member_id: str | None = Field(default=None, alias="memberId")
    leave_type_id: str | None = Field(default=None, alias="leaveTypeId")

    model_config = {"populate_by_name": True}


class LeaveBalanceUpsertRequest(BaseModel):
    member_id: str = Field(..., alias="memberId")
    leave_type_id: str = Field(..., alias="leaveTypeId")
    year: int = Field(..., ge=2000, le=3000)
    allocated: float = Field(..., ge=0)
    carried_forward: float = Field(default=0, alias="carriedForward", ge=0)
    lapsed: float = Field(default=0, ge=0)

    model_config = {"populate_by_name": True}


class HolidayListFilters(BaseModel):
    year: int | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    search: str | None = Field(default=None, max_length=255)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    model_config = {"populate_by_name": True}


class HolidayListResponse(BaseModel):
    items: list[HolidayResponse]
    total: int
    page: int
    page_size: int


class LeaveCalendarFilters(BaseModel):
    year: int | None = None
    month: int | None = Field(default=None, ge=1, le=12)
    from_date: dt.date | None = Field(default=None, alias="fromDate")
    to_date: dt.date | None = Field(default=None, alias="toDate")

    model_config = {"populate_by_name": True}


class LeaveTypeResponse(BaseModel):
    id: str
    organization_id: str = Field(alias="organizationId")
    name: str
    quota: float
    carry_forward: bool = Field(alias="carryForward")
    is_paid: bool = Field(alias="isPaid")
    color: str | None
    created_at: dt.datetime = Field(alias="createdAt")
    updated_at: dt.datetime = Field(alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class MemberSummaryResponse(BaseModel):
    member_id: str = Field(alias="memberId")
    user_id: str = Field(alias="userId")
    name: str | None
    email: str | None

    model_config = {"populate_by_name": True}


class LeaveRequestResponse(BaseModel):
    id: str
    organization_id: str = Field(alias="organizationId")
    member_id: str = Field(alias="memberId")
    leave_type_id: str = Field(alias="leaveTypeId")
    start_date: dt.date = Field(alias="startDate")
    end_date: dt.date = Field(alias="endDate")
    days: float
    reason: str | None
    status: LeaveRequestStatus
    approved_by_id: str | None = Field(alias="approvedById")
    approver_comment: str | None = Field(alias="approverComment")
    cancelled_at: dt.datetime | None = Field(alias="cancelledAt")
    created_at: dt.datetime = Field(alias="createdAt")
    updated_at: dt.datetime = Field(alias="updatedAt")
    member: MemberSummaryResponse
    approver: MemberSummaryResponse | None
    leave_type: LeaveTypeResponse = Field(alias="leaveType")

    model_config = {"populate_by_name": True}


class LeaveRequestListResponse(BaseModel):
    items: list[LeaveRequestResponse]
    total: int
    page: int
    page_size: int


class HolidayResponse(BaseModel):
    id: str
    organization_id: str = Field(alias="organizationId")
    name: str
    holiday_date: dt.date = Field(alias="holidayDate")
    is_holiday: bool = Field(alias="isHoliday")
    is_recurring: bool = Field(alias="isRecurring")
    description: str | None
    created_at: dt.datetime = Field(alias="createdAt")
    updated_at: dt.datetime = Field(alias="updatedAt")

    model_config = {"from_attributes": True, "populate_by_name": True}


class LeaveBalanceResponse(BaseModel):
    id: str
    organization_id: str = Field(alias="organizationId")
    member_id: str = Field(alias="memberId")
    leave_type_id: str = Field(alias="leaveTypeId")
    year: int
    allocated: float
    used: float
    remaining: float
    carried_forward: float = Field(alias="carriedForward")
    lapsed: float
    created_at: dt.datetime = Field(alias="createdAt")
    updated_at: dt.datetime = Field(alias="updatedAt")
    member: MemberSummaryResponse
    leave_type: LeaveTypeResponse = Field(alias="leaveType")

    model_config = {"populate_by_name": True}


class LeaveBalanceListResponse(BaseModel):
    items: list[LeaveBalanceResponse]
    total: int


class LeaveCalendarResponse(BaseModel):
    holidays: list[HolidayResponse]
    leave_requests: list[LeaveRequestResponse] = Field(alias="leaveRequests")

    model_config = {"populate_by_name": True}
