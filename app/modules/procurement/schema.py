from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

PROCUREMENT_REQUEST_TYPES = ("BULK", "REPLACEMENT")
PROCUREMENT_STATUSES = (
    "DRAFT",
    "PENDING",
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


class AssetPurchaseRequisitionUpdateRequest(BaseModel):
    justification: str | None = Field(default=None, min_length=1)
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
    replacementReason: str | None = None

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = _normalize_enum(value)
        if normalized not in PROCUREMENT_URGENCY:
            raise ValueError("Invalid urgency")
        return normalized


class ProcurementPurchaseOrderCompanyPayload(BaseModel):
    displayName: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    logoUrl: str | None = Field(default=None, max_length=512)
    address: str | None = Field(default=None, max_length=500)
    contactEmail: str | None = Field(default=None, max_length=255)
    contactPhone: str | None = Field(default=None, max_length=80)
    taxId: str | None = Field(default=None, max_length=120)


class ProcurementPurchaseOrderTemplateVisibilityPayload(BaseModel):
    showLogo: bool = True
    showVendorContact: bool = True
    showVendorAddress: bool = True
    showBillingAddress: bool = True
    showShippingAddress: bool = True
    showSubject: bool = True
    showPaymentTerms: bool = True
    showNotes: bool = True
    showTerms: bool = True
    showFooter: bool = True
    showSignature: bool = True


class ProcurementPurchaseOrderSignatoryPayload(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    signatureImageUrl: str | None = Field(default=None, max_length=512)


class ProcurementPurchaseOrderTemplatePayload(BaseModel):
    name: str = Field(default="Default Purchase Order", min_length=1, max_length=160)
    pageSize: Literal["A4", "LETTER"] = "A4"
    locale: str = Field(default="en-IN", min_length=2, max_length=16)
    language: str = Field(default="en", min_length=2, max_length=16)
    headerTitle: str = Field(default="Purchase Order", min_length=1, max_length=255)
    headerSubtitle: str | None = Field(default=None, max_length=255)
    headerRichText: str | None = None
    footerRichText: str | None = None
    company: ProcurementPurchaseOrderCompanyPayload
    signatory: ProcurementPurchaseOrderSignatoryPayload
    visibility: ProcurementPurchaseOrderTemplateVisibilityPayload = Field(
        default_factory=ProcurementPurchaseOrderTemplateVisibilityPayload
    )
    defaultPaymentTermsHtml: str | None = None
    defaultNotesHtml: str | None = None
    defaultTermsHtml: str | None = None


class ProcurementPurchaseOrderVendorPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contactPerson: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=80)
    address: str | None = Field(default=None, max_length=500)
    taxId: str | None = Field(default=None, max_length=120)


class ProcurementPurchaseOrderDocumentPayload(BaseModel):
    vendor: ProcurementPurchaseOrderVendorPayload
    purchaseOrderDate: date
    deliveryDate: date | None = None
    billingAddress: str | None = Field(default=None, max_length=500)
    shippingAddress: str | None = Field(default=None, max_length=500)
    shippingMethod: str | None = Field(default=None, max_length=160)
    currency: str = Field(default="INR", min_length=3, max_length=12)
    subject: str | None = Field(default=None, max_length=255)
    paymentTermsHtml: str | None = None
    notesHtml: str | None = None
    termsHtml: str | None = None
    footerNotesHtml: str | None = None


class ProcurementPurchaseOrderLineItemPayload(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=120)
    quantity: int = Field(ge=1)
    unitPrice: float = Field(ge=0)
    taxPercent: float = Field(default=0, ge=0, le=100)
    total: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_total(self) -> "ProcurementPurchaseOrderLineItemPayload":
        computed_total = round(self.quantity * self.unitPrice * (1 + (self.taxPercent / 100)), 2)
        self.total = round(self.total, 2)
        if abs(self.total - computed_total) > 0.05:
            raise ValueError("Line item total does not match quantity, unit price, and tax")
        return self


class ProcurementPurchaseOrderDraftPayload(BaseModel):
    document: ProcurementPurchaseOrderDocumentPayload
    lineItems: list[ProcurementPurchaseOrderLineItemPayload] = Field(min_length=1)


class ProcurementPurchaseOrderTemplateUpdateRequest(BaseModel):
    template: ProcurementPurchaseOrderTemplatePayload


class ProcurementPurchaseOrderTemplateRead(BaseModel):
    id: str | None = None
    name: str
    status: str
    templateVersion: str
    updatedAt: datetime | None = None
    template: ProcurementPurchaseOrderTemplatePayload


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ProcurementPurchaseOrderPreviewRequest(BaseModel):
    formatKey: Literal["STANDARD"] = "STANDARD"
    template: ProcurementPurchaseOrderTemplatePayload
    document: ProcurementPurchaseOrderDraftPayload


class ProcurementPurchaseOrderGenerateRequest(ProcurementPurchaseOrderPreviewRequest):
    recipientMemberId: str | None = Field(default=None, max_length=36)
    recipientEmail: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=1000)
    sendToAdmin: bool = False

    @field_validator("recipientEmail")
    @classmethod
    def validate_optional_recipient_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid recipient email is required")
        return normalized

    @model_validator(mode="after")
    def validate_send_target(self) -> "ProcurementPurchaseOrderGenerateRequest":
        if self.sendToAdmin and (not self.recipientMemberId or not self.recipientEmail):
            raise ValueError("Recipient member and email are required when send to admin is enabled")
        return self


class ProcurementPdfPreviewResponse(BaseModel):
    fileName: str
    base64: str
    contentType: str = "application/pdf"


class ProcurementOrganizationDraftRead(BaseModel):
    name: str
    logoUrl: str | None = None


class ProcurementPurchaseOrderDraftResponse(BaseModel):
    requisition: "AssetPurchaseRequisitionRead"
    organization: ProcurementOrganizationDraftRead
    adminRecipients: list[ProcurementAdminRecipientOption]
    emailConfigured: bool
    templateVersion: str
    templateRecordId: str | None = None
    template: ProcurementPurchaseOrderTemplatePayload
    document: ProcurementPurchaseOrderDraftPayload


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
    templateVersion: str
    templateData: dict[str, Any]
    sentAt: datetime | None
    emailSubject: str | None
    emailError: str | None
    createdAt: datetime
    updatedAt: datetime


class ProcurementPurchaseOrderListItemRead(BaseModel):
    id: str
    poNumber: str
    status: str
    fileName: str
    generatedAt: datetime
    generatedByName: str | None
    recipientName: str | None
    recipientEmail: str
    requestLabel: str | None
    assetName: str | None
    storageBucket: str
    storagePath: str


class ProcurementPurchaseOrderDownloadResponse(BaseModel):
    fileName: str
    downloadUrl: str
    expiresInSeconds: int


class ProcurementPurchaseOrderIssueResponse(BaseModel):
    requisition: "AssetPurchaseRequisitionRead"
    purchaseOrderId: str
    poNumber: str
    status: str
    pdf: ProcurementPdfPreviewResponse


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


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int


class AssetPurchaseRequisitionListResponse(BaseModel):
    items: list[AssetPurchaseRequisitionRead]
    pagination: PaginationMeta


class ProcurementPurchaseOrderListResponse(BaseModel):
    items: list[ProcurementPurchaseOrderListItemRead]
    pagination: PaginationMeta


ProcurementPurchaseOrderDraftResponse.model_rebuild()
