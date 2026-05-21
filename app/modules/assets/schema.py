from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

ASSET_STATUSES = {
    "AVAILABLE",
    "PROVIDED",
    "UNDER_MAINTENANCE",
    "DAMAGED",
    "LOST",
    "RETIRED",
    "DISPOSED",
}
ASSET_CONDITIONS = {"NEW", "GOOD", "FAIR", "DAMAGED", "NEEDS_REPAIR"}
MAINTENANCE_TYPES = {
    "REPAIR",
    "SERVICE",
    "INSPECTION",
    "REPLACEMENT",
    "UPGRADE",
    "WARRANTY_CLAIM",
    "DAMAGE_CHECK",
}
MAINTENANCE_STATUSES = {"OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"}
TICKET_MODES = {"ASSET_ISSUE", "GENERAL_HELP_REQUEST"}
REPORT_TYPES = {
    "ALL_ASSETS",
    "AVAILABLE_ASSETS",
    "PROVIDED_ASSETS",
    "DAMAGED_ASSETS",
    "RETURNED_ASSETS",
    "MAINTENANCE_HISTORY",
    "EMPLOYEE_ASSET_REPORT",
    "OFFBOARDING_PENDING_RETURN",
}
CATEGORY_FIELD_TYPES = {"TEXT", "NUMBER", "DATE", "BOOLEAN", "SELECT"}


def _normalize_enum(value: str) -> str:
    return value.strip().upper().replace("-", "_").replace(" ", "_")


# ── Asset ID Schemas ─────────────────────────────────────────────────────────


class AssetIdCreate(BaseModel):
    assetIdName: str = Field(min_length=1, max_length=120)


class AssetIdUpdate(BaseModel):
    assetIdName: str | None = Field(default=None, min_length=1, max_length=120)


class AssetIdResponse(BaseModel):
    id: str
    assetIdName: str
    isActive: bool


# ── Category & Field Schemas ─────────────────────────────────────────────────


class CategoryFieldDefinitionCreate(BaseModel):
    fieldName: str = Field(min_length=1, max_length=100)
    fieldType: str
    fieldOptions: list[str] | None = None
    isRequired: bool = False
    displayOrder: int = 0

    @field_validator("fieldType")
    @classmethod
    def validate_field_type(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in CATEGORY_FIELD_TYPES:
            raise ValueError(
                f"Invalid field type. Must be one of: {', '.join(sorted(CATEGORY_FIELD_TYPES))}"
            )
        return normalized


class CategoryFieldDefinitionUpdate(BaseModel):
    fieldName: str | None = Field(default=None, min_length=1, max_length=100)
    fieldType: str | None = None
    fieldOptions: list[str] | None = None
    isRequired: bool | None = None
    displayOrder: int | None = None

    @field_validator("fieldType")
    @classmethod
    def validate_field_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _normalize_enum(value)
        if normalized not in CATEGORY_FIELD_TYPES:
            raise ValueError(
                f"Invalid field type. Must be one of: {', '.join(sorted(CATEGORY_FIELD_TYPES))}"
            )
        return normalized


class CategoryFieldDefinitionResponse(BaseModel):
    id: str
    categoryId: str
    fieldName: str
    fieldType: str
    fieldOptions: dict | None = None
    isRequired: bool
    displayOrder: int


class AssetCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    assetCode: str | None = Field(default=None, max_length=120)
    description: str | None = None


class AssetCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    assetCode: str | None = Field(default=None, max_length=120)
    description: str | None = None


class AssetCategoryResponse(BaseModel):
    id: str
    name: str
    assetCode: str | None = None
    description: str | None = None
    isActive: bool
    fields: list[CategoryFieldDefinitionResponse] = []


# ── Custom Field Value Schemas ────────────────────────────────────────────────


class CustomFieldValueInput(BaseModel):
    fieldDefinitionId: str
    value: str | None = None


class CustomFieldValueResponse(BaseModel):
    fieldDefinitionId: str
    fieldName: str
    fieldType: str
    value: str | None


# ── Unit Schemas ──────────────────────────────────────────────────────────────


class AssetUnitInput(BaseModel):
    serialNumber: str | None = None


class AssetUnitResponse(BaseModel):
    id: str
    assetId: str
    serialNumber: str | None
    status: str
    currentHolderMemberId: str | None
    currentHolderName: str | None
    condition: str | None


class AssetUnitSummary(BaseModel):
    total: int = 0
    available: int = 0
    provided: int = 0
    underMaintenance: int = 0
    damaged: int = 0


# ── Existing Asset Schemas (modified) ─────────────────────────────────────────


class AssetFilters(BaseModel):
    search: str | None = None
    category: str | None = None
    categoryDefinitionId: str | None = None
    status: str | None = None
    currentHolderMemberId: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=5000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _normalize_enum(value)
        if normalized not in ASSET_STATUSES:
            raise ValueError("Invalid asset status")
        return normalized


class AssetUpsertRequest(BaseModel):
    assetCode: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    category: str | None = None
    categoryDefinitionId: str | None = None
    serialNumber: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=120)
    purchaseDate: date | None = None
    purchasePrice: float | None = Field(default=None, ge=0)
    warrantyExpiryDate: date | None = None
    condition: str = Field(default="GOOD")
    status: str = Field(default="AVAILABLE")
    location: str | None = Field(default=None, max_length=160)
    notes: str | None = None
    quantity: int = Field(default=1, ge=1)
    customFields: list[CustomFieldValueInput] = []
    units: list[AssetUnitInput] = []

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in ASSET_CONDITIONS:
            raise ValueError("Invalid asset condition")
        return normalized

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in ASSET_STATUSES:
            raise ValueError("Invalid asset status")
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> AssetUpsertRequest:
        if (
            self.purchaseDate
            and self.warrantyExpiryDate
            and self.warrantyExpiryDate < self.purchaseDate
        ):
            raise ValueError("Warranty expiry date must be on or after the purchase date")
        return self


class AssetReturnRequest(BaseModel):
    memberId: str
    assetUnitId: str | None = None
    returnDate: datetime | None = None
    returnedCondition: str
    receivedByMemberId: str | None = None
    returnNotes: str | None = None
    nextStatus: str | None = None

    @field_validator("returnedCondition")
    @classmethod
    def validate_condition(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in ASSET_CONDITIONS:
            raise ValueError("Invalid returned condition")
        return normalized

    @field_validator("nextStatus")
    @classmethod
    def validate_next_status(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = _normalize_enum(value)
        if normalized not in {"AVAILABLE", "UNDER_MAINTENANCE", "DAMAGED", "RETIRED", "DISPOSED"}:
            raise ValueError("Invalid next asset status")
        return normalized


class AssetMaintenanceCreateRequest(BaseModel):
    maintenanceType: str
    issueDescription: str = Field(min_length=1)
    serviceDate: date
    expectedCompletionDate: date | None = None
    cost: float | None = Field(default=None, ge=0)
    status: str = Field(default="OPEN")
    category: str | None = Field(default=None, max_length=80)
    subject: str | None = Field(default=None, max_length=160)
    attachmentsMetadata: list[dict[str, str | int | float | bool | None]] = []
    conditionBeforeMaintenance: str | None = None
    notes: str | None = None
    assetUnitId: str | None = None

    @field_validator("maintenanceType")
    @classmethod
    def validate_maintenance_type(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in MAINTENANCE_TYPES:
            raise ValueError("Invalid maintenance type")
        return normalized

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in {"OPEN", "IN_PROGRESS"}:
            raise ValueError("Maintenance can only start as open or in progress")
        return normalized

    @field_validator("conditionBeforeMaintenance")
    @classmethod
    def validate_condition(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = _normalize_enum(value)
        if normalized not in ASSET_CONDITIONS:
            raise ValueError("Invalid condition before maintenance")
        return normalized


class AssetMaintenanceUpdateRequest(BaseModel):
    status: str
    expectedCompletionDate: date | None = None
    completedDate: date | None = None
    conditionAfterMaintenance: str | None = None
    nextAssetStatus: str | None = None
    notes: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in MAINTENANCE_STATUSES:
            raise ValueError("Invalid maintenance status")
        return normalized

    @field_validator("conditionAfterMaintenance")
    @classmethod
    def validate_condition(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = _normalize_enum(value)
        if normalized not in ASSET_CONDITIONS:
            raise ValueError("Invalid condition after maintenance")
        return normalized

    @field_validator("nextAssetStatus")
    @classmethod
    def validate_next_asset_status(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = _normalize_enum(value)
        if normalized not in {"AVAILABLE", "DAMAGED", "RETIRED", "DISPOSED", "UNDER_MAINTENANCE"}:
            raise ValueError("Invalid next asset status")
        return normalized

    @model_validator(mode="after")
    def validate_completion(self) -> AssetMaintenanceUpdateRequest:
        if self.status == "COMPLETED":
            if self.completedDate is None:
                raise ValueError("Completed date is required when maintenance is completed")
            if self.nextAssetStatus is None:
                raise ValueError("Next asset status is required when maintenance is completed")
        return self


class HelpdeskTicketCreateRequest(BaseModel):
    ticketMode: str = Field(default="GENERAL_HELP_REQUEST")
    assetId: str | None = None
    assetUnitId: str | None = None
    category: str | None = Field(default=None, max_length=80)
    subject: str = Field(min_length=1, max_length=160)
    issueDescription: str = Field(min_length=1)
    attachmentsMetadata: list[dict[str, str | int | float | bool | None]] = []
    maintenanceType: str = Field(default="REPAIR")
    serviceDate: date | None = None
    expectedCompletionDate: date | None = None
    conditionBeforeMaintenance: str | None = None
    notes: str | None = None

    @field_validator("ticketMode")
    @classmethod
    def validate_ticket_mode(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in TICKET_MODES:
            raise ValueError("Invalid ticket mode")
        return normalized

    @field_validator("maintenanceType")
    @classmethod
    def validate_maintenance_type(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in MAINTENANCE_TYPES:
            raise ValueError("Invalid maintenance type")
        return normalized

    @field_validator("conditionBeforeMaintenance")
    @classmethod
    def validate_condition(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        normalized = _normalize_enum(value)
        if normalized not in ASSET_CONDITIONS:
            raise ValueError("Invalid condition before maintenance")
        return normalized

    @model_validator(mode="after")
    def validate_asset_linkage(self) -> HelpdeskTicketCreateRequest:
        if self.ticketMode == "ASSET_ISSUE" and self.assetId is None:
            raise ValueError("Asset issue tickets require assetId")
        if self.ticketMode == "GENERAL_HELP_REQUEST" and self.assetUnitId is not None:
            raise ValueError("General help requests cannot be linked to an asset unit")
        return self


class AssetReportRequest(BaseModel):
    reportType: str
    memberId: str | None = None

    @field_validator("reportType")
    @classmethod
    def validate_report_type(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in REPORT_TYPES:
            raise ValueError("Invalid report type")
        return normalized


class AssetLookupOption(BaseModel):
    id: str
    label: str
    email: str | None = None


class AssetProvideRecordSummary(BaseModel):
    id: str
    assetUnitId: str | None
    memberId: str
    memberName: str | None
    memberEmail: str | None
    providedByMemberId: str | None
    providedByName: str | None
    providedDate: datetime
    conditionWhileProviding: str
    provideNotes: str | None
    returnDate: datetime | None
    returnedCondition: str | None
    receivedByMemberId: str | None
    receivedByName: str | None
    returnNotes: str | None


# ── New Bulk Create / Issue Schemas ──────────────────────────────────────────


class BulkAssetCreateRequest(BaseModel):
    assetCode: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=255)
    categoryDefinitionId: str | None = None
    condition: str = Field(default="GOOD")
    location: str | None = Field(default=None, max_length=160)
    serialNumbers: list[str] = Field(min_length=1)
    customFields: list[CustomFieldValueInput] = []

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in ASSET_CONDITIONS:
            raise ValueError("Invalid asset condition")
        return normalized

    @model_validator(mode="after")
    def validate_serials(self) -> BulkAssetCreateRequest:
        seen = set()
        for s in self.serialNumbers:
            if not s or not s.strip():
                raise ValueError("Serial number cannot be empty")
            if s.strip() in seen:
                raise ValueError("Duplicate serial numbers in the same submission")
            seen.add(s.strip())
        return self


class AvailableAssetGroupResponse(BaseModel):
    groupKey: str
    assetName: str
    categoryName: str | None = None
    categoryDefinitionId: str | None = None
    assetCode: str
    model: str | None = None
    availableQuantity: int


class AssetIssueRequest(BaseModel):
    memberId: str
    groupKey: str
    quantity: int = Field(ge=1)
    conditionWhileProviding: str
    providedByMemberId: str | None = None
    notes: str | None = None

    @field_validator("conditionWhileProviding")
    @classmethod
    def validate_condition(cls, value: str) -> str:
        normalized = _normalize_enum(value)
        if normalized not in ASSET_CONDITIONS:
            raise ValueError("Invalid condition while providing")
        return normalized


class AssetIssueResponse(BaseModel):
    issuedAssetIds: list[str]
    assignmentIds: list[str]


# ── Maintenance Summary ─────────────────────────────────────────────────────


class AssetMaintenanceSummary(BaseModel):
    id: str
    ticketId: str
    ticketMode: str
    assetId: str | None
    assetUnitId: str | None
    category: str | None
    subject: str | None
    attachmentsMetadata: list[dict[str, str | int | float | bool | None]]
    maintenanceType: str
    issueDescription: str
    serviceDate: date
    expectedCompletionDate: date | None
    completedDate: date | None
    cost: float | None
    status: str
    conditionBeforeMaintenance: str | None
    conditionAfterMaintenance: str | None
    notes: str | None
    loggedByMemberId: str | None
    loggedByName: str | None


class AssetSummary(BaseModel):
    id: str
    assetCode: str
    name: str
    category: str
    categoryDefinitionId: str | None
    serialNumber: str | None
    model: str | None
    purchaseDate: date | None
    purchasePrice: float | None
    warrantyExpiryDate: date | None
    condition: str
    status: str
    location: str | None
    notes: str | None
    quantity: int
    createdAt: datetime
    updatedAt: datetime
    currentHolderMemberId: str | None
    currentHolderName: str | None
    currentHolderEmail: str | None
    openMaintenanceCount: int
    unitSummary: AssetUnitSummary | None = None
    customFields: list[CustomFieldValueResponse] = []


class AssetDetailResponse(AssetSummary):
    activeProvision: AssetProvideRecordSummary | None
    assetHistory: list[AssetProvideRecordSummary]
    maintenanceHistory: list[AssetMaintenanceSummary]
    units: list[AssetUnitResponse] = []


class AssetListResponse(BaseModel):
    items: list[AssetSummary]
    total: int
    page: int
    page_size: int
    overdue_count: int


class AssetMetaResponse(BaseModel):
    members: list[AssetLookupOption]
    categories: list[AssetCategoryResponse]
    statuses: list[str]
    conditions: list[str]
    maintenanceTypes: list[str]
    maintenanceStatuses: list[str]
    ticketModes: list[str]
    reportTypes: list[str]


class AssetStatusCount(BaseModel):
    name: str
    value: int
    color: str


class MonthlyTrend(BaseModel):
    month: str
    count: int


class RecentActivityItem(BaseModel):
    type: str
    assetName: str
    memberName: str | None = None
    date: str
    detail: str | None = None


class TicketAlertItem(BaseModel):
    id: str
    ticketId: str
    ticketMode: str
    assetName: str | None
    category: str | None = None
    subject: str | None = None
    maintenanceType: str
    status: str
    issueDescription: str
    createdAt: str


class AssetDashboardResponse(BaseModel):
    totalAssets: int
    availableCount: int
    providedCount: int
    maintenanceCount: int
    damagedCount: int
    retiredCount: int
    openTicketCount: int
    statusDistribution: list[AssetStatusCount]
    monthlyTrends: list[MonthlyTrend]
    recentActivity: list[RecentActivityItem]
    recentTickets: list[TicketAlertItem]


class MyTicketResponse(BaseModel):
    id: str
    ticketId: str
    ticketMode: str
    assetId: str | None
    assetName: str | None
    assetCode: str | None
    category: str | None
    subject: str | None
    attachmentsMetadata: list[dict[str, str | int | float | bool | None]]
    maintenanceType: str
    issueDescription: str
    status: str
    serviceDate: str
    createdAt: str


class MaintenanceTicketResponse(BaseModel):
    id: str
    ticketId: str
    ticketMode: str
    assetId: str | None
    assetName: str | None
    assetCode: str | None
    assetCondition: str | None
    category: str | None
    subject: str | None
    attachmentsMetadata: list[dict[str, str | int | float | bool | None]]
    maintenanceType: str
    issueDescription: str
    status: str
    serviceDate: str
    createdAt: str
    loggedByMemberId: str | None = None
    loggedByName: str | None = None
