from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

ASSET_CATEGORIES = {"ELECTRONICS", "ID_CARD", "OTHER"}
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
REPORT_TYPES = {
    "ALL_ASSETS",
    "AVAILABLE_ASSETS",
    "MAINTENANCE_HISTORY",
}


def _normalize_enum(value: str) -> str:
    return value.strip().upper().replace("-", "_").replace(" ", "_")


def _normalize_category(value: str) -> str:
    normalized = _normalize_enum(value)
    if normalized in {"LAPTOP", "PHONE", "ACCESS_CARD", "PERIPHERAL"}:
        return "ELECTRONICS"
    return normalized


class AssetFilters(BaseModel):
    search: str | None = None
    category: str | None = None
    status: str | None = None
    currentHolderMemberId: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _normalize_category(value)
        if normalized not in ASSET_CATEGORIES:
            raise ValueError("Invalid asset category")
        return normalized

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
    category: str
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

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        normalized = _normalize_category(value)
        if normalized not in ASSET_CATEGORIES:
            raise ValueError("Invalid asset category")
        return normalized

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
        if self.purchaseDate and self.warrantyExpiryDate and self.warrantyExpiryDate < self.purchaseDate:
            raise ValueError("Warranty expiry date must be on or after the purchase date")
        return self


class AssetProvideRequest(BaseModel):
    memberId: str
    providedDate: datetime | None = None
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


class AssetReturnRequest(BaseModel):
    memberId: str
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
    conditionBeforeMaintenance: str | None = None
    notes: str | None = None

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


class AssetMaintenanceSummary(BaseModel):
    id: str
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


class AssetDetailResponse(AssetSummary):
    activeProvision: AssetProvideRecordSummary | None
    assetHistory: list[AssetProvideRecordSummary]
    maintenanceHistory: list[AssetMaintenanceSummary]


class AssetListResponse(BaseModel):
    items: list[AssetSummary]
    total: int
    page: int
    page_size: int
    overdue_count: int


class AssetMetaResponse(BaseModel):
    members: list[AssetLookupOption]
    categories: list[str]
    statuses: list[str]
    conditions: list[str]
    maintenanceTypes: list[str]
    maintenanceStatuses: list[str]
    reportTypes: list[str]
