from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

PROCUREMENT_REQUEST_TYPES = ("BULK", "REPLACEMENT")
PROCUREMENT_STATUSES = (
    "DRAFT",
    "PENDING_FINANCE_APPROVAL",
    "APPROVED",
    "REJECTED",
    "CANCELLED",
)
PROCUREMENT_PO_STATUSES = ("GENERATED", "SENT", "FAILED", "CANCELLED")
PROCUREMENT_PO_FORMATS = ("STANDARD",)
PROCUREMENT_URGENCY = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
WARRANTY_STATUSES = ("IN_WARRANTY", "EXPIRED", "UNKNOWN")


def _normalize_enum(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().upper().replace("-", "_").replace(" ", "_")


class ProcurementDepartmentOption(BaseModel):
    id: str
    name: str


class ProcurementCategoryOption(BaseModel):
    id: str
    name: str
    assetCode: str | None = None


class ProcurementReplacementTicketOption(BaseModel):
    id: str
    ticketId: str
    subject: str | None = None
    issueDescription: str
    status: str
    serviceDate: str
    maintenanceType: str
    assetId: str | None = None
    assetUnitId: str | None = None
    assetName: str | None = None
    assetCode: str | None = None
    serialNumber: str | None = None
    currentCondition: str | None = None
    originalPurchaseDate: str | None = None
    warrantyExpiryDate: str | None = None
    warrantyStatus: str
    affectedEmployeeId: str | None = None
    affectedEmployeeName: str | None = None
    raisedByName: str | None = None
    replacementMode: str | None = None
    createdAt: str


class ProcurementMetaResponse(BaseModel):
    departments: list[ProcurementDepartmentOption]
    categories: list[ProcurementCategoryOption]
    replacementTickets: list[ProcurementReplacementTicketOption]


class ProcurementAdminRecipientOption(BaseModel):
    memberId: str
    name: str
    email: str


class ProcurementAdminRecipientsResponse(BaseModel):
    items: list[ProcurementAdminRecipientOption]


class AssetPurchaseRequisitionCreateRequest(BaseModel):
    requestType: str
    justification: str = Field(min_length=1)
    requiredByDate: date | None = None
    estimatedUnitCost: float | None = Field(default=None, ge=0)
    estimatedQuantity: int | None = Field(default=None, ge=1)
    estimatedTotalCost: float | None = Field(default=None, ge=0)
    vendorPreference: str | None = Field(default=None, max_length=160)
    urgency: str | None = None
    costCenterOrDepartmentId: str | None = None
    assetName: str | None = Field(default=None, max_length=255)
    assetCode: str | None = Field(default=None, max_length=120)
    categoryDefinitionId: str | None = None
    specificationNotes: str | None = None
    maintenanceTicketId: str | None = None
    replacementReason: str | None = None

    @field_validator("requestType")
    @classmethod
    def validate_request_type(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in PROCUREMENT_REQUEST_TYPES:
            raise ValueError("Invalid requisition type")
        return normalized

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = _normalize_enum(value)
        if normalized not in PROCUREMENT_URGENCY:
            raise ValueError("Invalid urgency")
        return normalized

    @model_validator(mode="after")
    def validate_shape(self) -> "AssetPurchaseRequisitionCreateRequest":
        if self.requestType == "BULK":
            if not (self.assetName or "").strip():
                raise ValueError("Asset name is required for bulk purchasing")
            if self.estimatedQuantity is None:
                raise ValueError("Quantity is required for bulk purchasing")
        if self.requestType == "REPLACEMENT":
            if not self.maintenanceTicketId:
                raise ValueError("Replacement purchasing requires a linked ticket")
            if not (self.replacementReason or "").strip():
                raise ValueError("Replacement reason is required")
            self.estimatedQuantity = 1
        if not (self.justification or "").strip():
            raise ValueError("Justification is required")
        return self


class ProcurementDecisionRequest(BaseModel):
    comment: str | None = None


class ProcurementPurchaseOrderCreateRequest(BaseModel):
    formatKey: str = Field(default="STANDARD", max_length=64)
    recipientMemberId: str = Field(min_length=1, max_length=36)
    recipientEmail: str = Field(min_length=3, max_length=255)
    message: str | None = Field(default=None, max_length=1000)

    @field_validator("formatKey")
    @classmethod
    def validate_format_key(cls, value: str) -> str:
        normalized = _normalize_enum(value) or "STANDARD"
        if normalized not in PROCUREMENT_PO_FORMATS:
            raise ValueError("Invalid purchase order format")
        return normalized

    @field_validator("recipientEmail")
    @classmethod
    def validate_recipient_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid recipient email is required")
        return normalized

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class ProcurementActivityEntry(BaseModel):
    id: str
    actorId: str | None
    actorName: str | None
    action: str
    comment: str | None
    createdAt: datetime


class ProcurementPurchaseOrderRead(BaseModel):
    id: str
    poNumber: str
    formatKey: str
    status: str
    storageBucket: str
    storagePath: str
    fileName: str
    recipientMemberId: str | None
    recipientName: str | None
    recipientEmail: str
    generatedByMemberId: str | None
    generatedByName: str | None
    generatedAt: datetime
    sentAt: datetime | None
    emailSubject: str | None
    emailError: str | None
    createdAt: datetime
    updatedAt: datetime


class ProcurementSnapshotRead(BaseModel):
    ticketId: str | None = None
    subject: str | None = None
    issueDescription: str | None = None
    status: str | None = None
    createdAt: str | None = None
    serviceDate: str | None = None
    maintenanceType: str | None = None
    assetName: str | None = None
    assetCode: str | None = None
    serialNumber: str | None = None
    affectedEmployeeName: str | None = None
    raisedByName: str | None = None
    currentCondition: str | None = None
    originalPurchaseDate: str | None = None
    warrantyExpiryDate: str | None = None
    warrantyStatus: str | None = None
    replacementMode: str | None = None


class AssetPurchaseRequisitionRead(BaseModel):
    id: str
    requestType: str
    status: str
    requestNumber: int | None
    requestLabel: str | None
    raisedByMemberId: str
    raisedByName: str | None
    approvedByMemberId: str | None
    approvedByName: str | None
    approvedAt: datetime | None
    rejectedAt: datetime | None
    reviewerComment: str | None
    justification: str
    requiredByDate: date | None
    estimatedUnitCost: float | None
    estimatedQuantity: int | None
    estimatedTotalCost: float | None
    vendorPreference: str | None
    urgency: str | None
    costCenterOrDepartmentId: str | None
    costCenterOrDepartmentName: str | None
    assetName: str | None
    assetCode: str | None
    categoryDefinitionId: str | None
    categoryName: str | None
    specificationNotes: str | None
    maintenanceTicketId: str | None
    assetId: str | None
    assetUnitId: str | None
    affectedEmployeeId: str | None
    affectedEmployeeName: str | None
    originalPurchaseDate: date | None
    warrantyExpiryDate: date | None
    warrantyStatus: str | None
    replacementReason: str | None
    replacementMode: str | None
    ticketSnapshot: ProcurementSnapshotRead | dict[str, Any] | None = None
    assetSnapshot: ProcurementSnapshotRead | dict[str, Any] | None = None
    createdAt: datetime
    updatedAt: datetime
    currentUserCanApprove: bool
    canSubmit: bool
    approvalsPendingFinance: bool
    activities: list[ProcurementActivityEntry]
    purchaseOrders: list[ProcurementPurchaseOrderRead]


class AssetPurchaseRequisitionListResponse(BaseModel):
    items: list[AssetPurchaseRequisitionRead]
