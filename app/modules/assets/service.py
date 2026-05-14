from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import Select, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.base import generate_uuid
from app.models.asset import Asset
from app.models.asset_assignment import AssetAssignment
from app.models.asset_category_definition import AssetCategoryDefinition
from app.models.asset_category_field_definition import AssetCategoryFieldDefinition
from app.models.asset_custom_field_value import AssetCustomFieldValue
from app.models.asset_maintenance_log import AssetMaintenanceLog
from app.models.asset_unit import AssetUnit
from app.models.asset_id_definition import AssetIdDefinition
from app.models.member import Member
from app.models.user import User
from app.modules.assets.schema import (
    AssetIdCreate,
    AssetIdUpdate,
    AssetIdResponse,
    ASSET_CONDITIONS,
    ASSET_STATUSES,
    MAINTENANCE_STATUSES,
    MAINTENANCE_TYPES,
    REPORT_TYPES,
    AssetCategoryCreate,
    AssetCategoryResponse,
    AssetCategoryUpdate,
    AssetDashboardResponse,
    AssetDetailResponse,
    AssetFilters,
    AssetListResponse,
    AssetLookupOption,
    AssetMaintenanceCreateRequest,
    AssetMaintenanceSummary,
    AssetMaintenanceUpdateRequest,
    AssetMetaResponse,
    AssetProvideRecordSummary,
    AssetProvideRequest,
    AssetReportRequest,
    AssetReturnRequest,
    AssetStatusCount,
    AssetSummary,
    AssetUnitResponse,
    AssetUnitSummary,
    AssetUpsertRequest,
    CategoryFieldDefinitionCreate,
    CategoryFieldDefinitionResponse,
    CategoryFieldDefinitionUpdate,
    CustomFieldValueResponse,
    MonthlyTrend,
    RecentActivityItem,
    TicketAlertItem,
)
from app.shared.deps.organization_member import MemberContext


def _to_title(value: str) -> str:
    return value.lower().replace("_", " ").title()


def _csv_to_pdf_bytes(report_type: str, csv_text: str) -> bytes:
    rows = list(csv.reader(io.StringIO(csv_text)))
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)

    page_width, page_height = A4
    margin = 36
    line_height = 13

    def draw_header() -> float:
        y_cursor = page_height - margin
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin, y_cursor, f"{_to_title(report_type)} Report")
        y_cursor -= 16
        pdf.setFont("Helvetica", 9)
        pdf.drawString(margin, y_cursor, f"Generated at: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}")
        y_cursor -= 18
        return y_cursor

    y = draw_header()
    for row_index, row in enumerate(rows):
        if y < margin:
            pdf.showPage()
            y = draw_header()

        pdf.setFont("Helvetica-Bold" if row_index == 0 else "Helvetica", 8 if row_index == 0 else 7.8)
        line_text = " | ".join((col or "").replace("\n", " ").strip() for col in row)
        if len(line_text) > 220:
            line_text = f"{line_text[:217]}..."
        pdf.drawString(margin, y, line_text)
        y -= line_height

    pdf.save()
    buffer.seek(0)
    return buffer.read()


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


async def _get_asset_or_404(db: AsyncSession, organization_id: str, asset_id: str) -> Asset:
    result = await db.execute(
        select(Asset)
        .where(
            Asset.id == asset_id,
            Asset.organizationId == organization_id,
            Asset.deletedAt.is_(None),
        )
        .options(
            joinedload(Asset.provisions),
            joinedload(Asset.maintenanceLogs),
            joinedload(Asset.units),
            joinedload(Asset.customFieldValues).joinedload(AssetCustomFieldValue.fieldDefinition),
        )
    )
    asset = result.unique().scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


async def _get_member_or_404(db: AsyncSession, organization_id: str, member_id: str) -> Member:
    result = await db.execute(
        select(Member)
        .where(Member.id == member_id, Member.organizationId == organization_id)
        .options(joinedload(Member.user))
    )
    member = result.unique().scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return member


async def _get_maintenance_or_404(db: AsyncSession, asset_id: str, maintenance_id: str) -> AssetMaintenanceLog:
    result = await db.execute(
        select(AssetMaintenanceLog).where(
            AssetMaintenanceLog.id == maintenance_id,
            AssetMaintenanceLog.assetId == asset_id,
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found")
    return log


async def _get_category_or_404(db: AsyncSession, organization_id: str, category_id: str) -> AssetCategoryDefinition:
    result = await db.execute(
        select(AssetCategoryDefinition)
        .where(
            AssetCategoryDefinition.id == category_id,
            AssetCategoryDefinition.organizationId == organization_id,
            AssetCategoryDefinition.isActive.is_(True),
        )
        .options(joinedload(AssetCategoryDefinition.fields))
    )
    category = result.unique().scalar_one_or_none()
    if category is None:
        raise HTTPException(status_code=404, detail="Asset category not found")
    return category


def _derive_asset_status(units: list[AssetUnit]) -> str:
    if not units:
        return "AVAILABLE"
    statuses = {u.status for u in units}
    if all(s == "AVAILABLE" for s in statuses):
        return "AVAILABLE"
    if all(s in ("RETIRED", "DISPOSED") for s in statuses):
        return "RETIRED"
    if "PROVIDED" in statuses:
        return "PROVIDED"
    if "UNDER_MAINTENANCE" in statuses:
        return "UNDER_MAINTENANCE"
    if "DAMAGED" in statuses:
        return "DAMAGED"
    if "LOST" in statuses:
        return "LOST"
    return "AVAILABLE"


def _unit_summary(units: list[AssetUnit]) -> AssetUnitSummary | None:
    if not units:
        return None
    summary = AssetUnitSummary(total=len(units))
    for unit in units:
        if unit.status == "AVAILABLE":
            summary.available += 1
        elif unit.status == "PROVIDED":
            summary.provided += 1
        elif unit.status == "UNDER_MAINTENANCE":
            summary.underMaintenance += 1
        elif unit.status == "DAMAGED":
            summary.damaged += 1
    return summary


async def _active_provision_map(db: AsyncSession, organization_id: str) -> dict[str, AssetAssignment]:
    result = await db.execute(
        select(AssetAssignment)
        .join(Asset, Asset.id == AssetAssignment.assetId)
        .where(
            Asset.organizationId == organization_id,
            Asset.deletedAt.is_(None),
            AssetAssignment.returnDate.is_(None),
        )
        .options(
            joinedload(AssetAssignment.member).joinedload(Member.user),
            joinedload(AssetAssignment.providedByMember).joinedload(Member.user),
            joinedload(AssetAssignment.receivedByMember).joinedload(Member.user),
        )
    )
    provisions = result.unique().scalars().all()
    return {provision.assetId: provision for provision in provisions}


def _asset_summary(asset: Asset, active_provision: AssetAssignment | None) -> AssetSummary:
    holder = active_provision.member.user if active_provision and active_provision.member and active_provision.member.user else None
    open_maintenance_count = sum(1 for log in asset.maintenanceLogs if log.status in {"OPEN", "IN_PROGRESS"})

    custom_fields = [
        CustomFieldValueResponse(
            fieldDefinitionId=cfv.fieldDefinitionId,
            fieldName=cfv.fieldDefinition.fieldName if cfv.fieldDefinition else "",
            fieldType=cfv.fieldDefinition.fieldType if cfv.fieldDefinition else "",
            value=cfv.value,
        )
        for cfv in asset.customFieldValues
        if cfv.fieldDefinition
    ]

    return AssetSummary(
        id=asset.id,
        assetCode=asset.assetCode,
        name=asset.name,
        category=asset.category,
        categoryDefinitionId=asset.categoryDefinitionId,
        serialNumber=asset.serialNumber,
        model=asset.model,
        purchaseDate=asset.purchaseDate,
        purchasePrice=_to_float(asset.purchasePrice),
        warrantyExpiryDate=asset.warrantyExpiryDate,
        condition=asset.condition,
        status=asset.status,
        location=asset.location,
        notes=asset.notes,
        quantity=asset.quantity,
        createdAt=asset.createdAt,
        updatedAt=asset.updatedAt,
        currentHolderMemberId=active_provision.memberId if active_provision else None,
        currentHolderName=holder.name if holder else None,
        currentHolderEmail=holder.email if holder else None,
        openMaintenanceCount=open_maintenance_count,
        unitSummary=_unit_summary(asset.units),
        customFields=custom_fields,
    )


def _provide_record_summary(record: AssetAssignment) -> AssetProvideRecordSummary:
    holder = record.member.user if record.member and record.member.user else None
    provider = record.providedByMember.user if record.providedByMember and record.providedByMember.user else None
    receiver = record.receivedByMember.user if record.receivedByMember and record.receivedByMember.user else None
    return AssetProvideRecordSummary(
        id=record.id,
        assetUnitId=record.assetUnitId,
        memberId=record.memberId,
        memberName=holder.name if holder else None,
        memberEmail=holder.email if holder else None,
        providedByMemberId=record.providedByMemberId,
        providedByName=provider.name if provider else None,
        providedDate=record.providedDate,
        conditionWhileProviding=record.conditionWhileProviding,
        provideNotes=record.provideNotes,
        returnDate=record.returnDate,
        returnedCondition=record.returnedCondition,
        receivedByMemberId=record.receivedByMemberId,
        receivedByName=receiver.name if receiver else None,
        returnNotes=record.returnNotes,
    )


def _maintenance_summary(log: AssetMaintenanceLog) -> AssetMaintenanceSummary:
    actor = log.loggedByMember.user if log.loggedByMember and log.loggedByMember.user else None
    return AssetMaintenanceSummary(
        id=log.id,
        assetUnitId=log.assetUnitId,
        maintenanceType=log.maintenanceType,
        issueDescription=log.issueDescription,
        serviceDate=log.serviceDate,
        expectedCompletionDate=log.expectedCompletionDate,
        completedDate=log.completedDate,
        cost=_to_float(log.cost),
        status=log.status,
        conditionBeforeMaintenance=log.conditionBeforeMaintenance,
        conditionAfterMaintenance=log.conditionAfterMaintenance,
        notes=log.notes,
        loggedByMemberId=log.loggedByMemberId,
        loggedByName=actor.name if actor else None,
    )


# ── Asset ID CRUD ────────────────────────────────────────────────────────────

async def create_asset_id(
    db: AsyncSession, ctx: MemberContext, payload: AssetIdCreate,
) -> AssetIdResponse:
    existing = await db.execute(
        select(AssetIdDefinition).where(
            AssetIdDefinition.organizationId == ctx.organization.id,
            AssetIdDefinition.assetIdName == payload.assetIdName.strip(),
            AssetIdDefinition.isActive.is_(True),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="An asset ID with this name already exists")
    asset_id = AssetIdDefinition(
        organizationId=ctx.organization.id,
        assetIdName=payload.assetIdName.strip(),
    )
    db.add(asset_id)
    await db.commit()
    return AssetIdResponse(
        id=asset_id.id, assetIdName=asset_id.assetIdName,
        isActive=asset_id.isActive,
    )


async def list_asset_ids(db: AsyncSession, ctx: MemberContext) -> list[AssetIdResponse]:
    result = await db.execute(
        select(AssetIdDefinition)
        .where(
            AssetIdDefinition.organizationId == ctx.organization.id,
            AssetIdDefinition.isActive.is_(True),
        )
        .order_by(AssetIdDefinition.assetIdName.asc())
    )
    items = result.scalars().all()
    return [
        AssetIdResponse(id=a.id, assetIdName=a.assetIdName, isActive=a.isActive)
        for a in items
    ]


async def update_asset_id(
    db: AsyncSession, ctx: MemberContext, asset_id_id: str, payload: AssetIdUpdate,
) -> AssetIdResponse:
    result = await db.execute(
        select(AssetIdDefinition).where(
            AssetIdDefinition.id == asset_id_id,
            AssetIdDefinition.organizationId == ctx.organization.id,
            AssetIdDefinition.isActive.is_(True),
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Asset ID not found")
    if payload.assetIdName is not None:
        dupe = await db.execute(
            select(AssetIdDefinition).where(
                AssetIdDefinition.organizationId == ctx.organization.id,
                AssetIdDefinition.assetIdName == payload.assetIdName.strip(),
                AssetIdDefinition.id != asset_id_id,
                AssetIdDefinition.isActive.is_(True),
            )
        )
        if dupe.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="An asset ID with this name already exists")
        entry.assetIdName = payload.assetIdName.strip()
    await db.commit()
    return AssetIdResponse(
        id=entry.id, assetIdName=entry.assetIdName,
        isActive=entry.isActive,
    )


async def delete_asset_id(db: AsyncSession, ctx: MemberContext, asset_id_id: str) -> None:
    result = await db.execute(
        select(AssetIdDefinition).where(
            AssetIdDefinition.id == asset_id_id,
            AssetIdDefinition.organizationId == ctx.organization.id,
            AssetIdDefinition.isActive.is_(True),
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Asset ID not found")
    entry.isActive = False
    await db.commit()


# ── Category CRUD ─────────────────────────────────────────────────────────────

async def create_category(
    db: AsyncSession,
    ctx: MemberContext,
    payload: AssetCategoryCreate,
) -> AssetCategoryResponse:
    existing = await db.execute(
        select(AssetCategoryDefinition).where(
            AssetCategoryDefinition.organizationId == ctx.organization.id,
            AssetCategoryDefinition.name == payload.name.strip(),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A category with this name already exists")

    category = AssetCategoryDefinition(
        organizationId=ctx.organization.id,
        name=payload.name.strip(),
    )
    db.add(category)
    await db.commit()

    return AssetCategoryResponse(
        id=category.id,
        name=category.name,
        isActive=category.isActive,
        fields=[],
    )


async def list_categories(db: AsyncSession, ctx: MemberContext) -> list[AssetCategoryResponse]:
    result = await db.execute(
        select(AssetCategoryDefinition)
        .where(
            AssetCategoryDefinition.organizationId == ctx.organization.id,
            AssetCategoryDefinition.isActive.is_(True),
        )
        .options(joinedload(AssetCategoryDefinition.fields))
        .order_by(AssetCategoryDefinition.name.asc())
    )
    categories = result.unique().scalars().all()
    return [
        AssetCategoryResponse(
            id=c.id,
            name=c.name,
            isActive=c.isActive,
            fields=[
                CategoryFieldDefinitionResponse(
                    id=f.id,
                    categoryId=f.categoryId,
                    fieldName=f.fieldName,
                    fieldType=f.fieldType,
                    fieldOptions=f.fieldOptions,
                    isRequired=f.isRequired,
                    displayOrder=f.displayOrder,
                )
                for f in (c.fields or [])
            ],
        )
        for c in categories
    ]


async def update_category(
    db: AsyncSession,
    ctx: MemberContext,
    category_id: str,
    payload: AssetCategoryUpdate,
) -> AssetCategoryResponse:
    category = await _get_category_or_404(db, ctx.organization.id, category_id)
    if payload.name is not None:
        existing = await db.execute(
            select(AssetCategoryDefinition).where(
                AssetCategoryDefinition.organizationId == ctx.organization.id,
                AssetCategoryDefinition.name == payload.name.strip(),
                AssetCategoryDefinition.id != category_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="A category with this name already exists")
        category.name = payload.name.strip()
    if payload.description is not None:
        category.description = payload.description.strip() if payload.description else None
    await db.commit()

    fields = [
        CategoryFieldDefinitionResponse(
            id=f.id,
            categoryId=f.categoryId,
            fieldName=f.fieldName,
            fieldType=f.fieldType,
            fieldOptions=f.fieldOptions,
            isRequired=f.isRequired,
            displayOrder=f.displayOrder,
        )
        for f in (category.fields or [])
    ]
    return AssetCategoryResponse(
        id=category.id,
        name=category.name,
        isActive=category.isActive,
        fields=fields,
    )


async def delete_category(db: AsyncSession, ctx: MemberContext, category_id: str) -> None:
    category = await _get_category_or_404(db, ctx.organization.id, category_id)
    assets_with_category = await db.execute(
        select(Asset).where(
            Asset.organizationId == ctx.organization.id,
            Asset.categoryDefinitionId == category_id,
            Asset.deletedAt.is_(None),
        ).limit(1)
    )
    if assets_with_category.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="Cannot delete category that has assets assigned to it")
    category.isActive = False
    await db.commit()


# ── Category Field CRUD ───────────────────────────────────────────────────────


async def create_category_field(
    db: AsyncSession,
    ctx: MemberContext,
    category_id: str,
    payload: CategoryFieldDefinitionCreate,
) -> CategoryFieldDefinitionResponse:
    await _get_category_or_404(db, ctx.organization.id, category_id)

    field = AssetCategoryFieldDefinition(
        categoryId=category_id,
        fieldName=payload.fieldName.strip(),
        fieldType=payload.fieldType,
        fieldOptions={"options": payload.fieldOptions} if payload.fieldOptions else None,
        isRequired=payload.isRequired,
        displayOrder=payload.displayOrder,
    )
    db.add(field)
    await db.commit()

    return CategoryFieldDefinitionResponse(
        id=field.id,
        categoryId=field.categoryId,
        fieldName=field.fieldName,
        fieldType=field.fieldType,
        fieldOptions=field.fieldOptions,
        isRequired=field.isRequired,
        displayOrder=field.displayOrder,
    )


async def update_category_field(
    db: AsyncSession,
    ctx: MemberContext,
    field_id: str,
    payload: CategoryFieldDefinitionUpdate,
) -> CategoryFieldDefinitionResponse:
    result = await db.execute(
        select(AssetCategoryFieldDefinition)
        .join(AssetCategoryDefinition, AssetCategoryDefinition.id == AssetCategoryFieldDefinition.categoryId)
        .where(
            AssetCategoryFieldDefinition.id == field_id,
            AssetCategoryDefinition.organizationId == ctx.organization.id,
        )
    )
    field = result.unique().scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=404, detail="Category field not found")

    if payload.fieldName is not None:
        field.fieldName = payload.fieldName.strip()
    if payload.fieldType is not None:
        field.fieldType = payload.fieldType
    if payload.fieldOptions is not None:
        field.fieldOptions = {"options": payload.fieldOptions} if payload.fieldOptions else None
    if payload.isRequired is not None:
        field.isRequired = payload.isRequired
    if payload.displayOrder is not None:
        field.displayOrder = payload.displayOrder
    await db.commit()

    return CategoryFieldDefinitionResponse(
        id=field.id,
        categoryId=field.categoryId,
        fieldName=field.fieldName,
        fieldType=field.fieldType,
        fieldOptions=field.fieldOptions,
        isRequired=field.isRequired,
        displayOrder=field.displayOrder,
    )


async def delete_category_field(db: AsyncSession, ctx: MemberContext, field_id: str) -> None:
    result = await db.execute(
        select(AssetCategoryFieldDefinition)
        .join(AssetCategoryDefinition, AssetCategoryDefinition.id == AssetCategoryFieldDefinition.categoryId)
        .where(
            AssetCategoryFieldDefinition.id == field_id,
            AssetCategoryDefinition.organizationId == ctx.organization.id,
        )
    )
    field = result.unique().scalar_one_or_none()
    if field is None:
        raise HTTPException(status_code=404, detail="Category field not found")

    await db.execute(
        select(AssetCustomFieldValue).where(AssetCustomFieldValue.fieldDefinitionId == field_id).limit(1)
    )
    await db.delete(field)
    await db.commit()


# ── Asset CRUD (modified) ──────────────────────────────────────────────────────


async def list_assets(db: AsyncSession, ctx: MemberContext, filters: AssetFilters) -> AssetListResponse:
    scope = getattr(ctx, "scope", "organization")

    active_provision_subquery = (
        select(
            AssetAssignment.assetId.label("assetId"),
            AssetAssignment.memberId.label("memberId"),
        )
        .where(AssetAssignment.returnDate.is_(None))
        .subquery()
    )

    query: Select = (
        select(Asset)
        .where(Asset.organizationId == ctx.organization.id, Asset.deletedAt.is_(None))
        .order_by(Asset.updatedAt.desc(), Asset.createdAt.desc())
    )
    joined_active_provision = False

    if scope == "self":
        query = query.join(active_provision_subquery, active_provision_subquery.c.assetId == Asset.id).where(
            active_provision_subquery.c.memberId == ctx.member.id
        )
        joined_active_provision = True

    if filters.currentHolderMemberId:
        if not joined_active_provision:
            query = query.join(active_provision_subquery, active_provision_subquery.c.assetId == Asset.id)
            joined_active_provision = True
        query = query.where(active_provision_subquery.c.memberId == filters.currentHolderMemberId)

    if filters.search:
        term = f"%{filters.search.strip()}%"
        query = query.where(
            or_(
                Asset.name.ilike(term),
                Asset.assetCode.ilike(term),
                Asset.serialNumber.ilike(term),
                Asset.model.ilike(term),
                Asset.location.ilike(term),
            )
        )
    if filters.category:
        query = query.where(Asset.category == filters.category)
    if filters.categoryDefinitionId:
        query = query.where(Asset.categoryDefinitionId == filters.categoryDefinitionId)
    if filters.status:
        query = query.where(Asset.status == filters.status)

    total_result = await db.execute(select(func.count()).select_from(query.order_by(None).subquery()))
    total = total_result.scalar_one()

    rows = await db.execute(
        query.offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
        .options(
            joinedload(Asset.provisions),
            joinedload(Asset.maintenanceLogs),
            joinedload(Asset.units),
            joinedload(Asset.customFieldValues).joinedload(AssetCustomFieldValue.fieldDefinition),
        )
    )
    assets = rows.unique().scalars().all()

    active_map = await _active_provision_map(db, ctx.organization.id)
    items = [_asset_summary(asset, active_map.get(asset.id)) for asset in assets]

    return AssetListResponse(
        items=items,
        total=total,
        page=filters.page,
        page_size=filters.page_size,
        overdue_count=0,
    )


async def get_asset(db: AsyncSession, ctx: MemberContext, asset_id: str) -> AssetDetailResponse:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)

    provisions_result = await db.execute(
        select(AssetAssignment)
        .where(AssetAssignment.assetId == asset_id)
        .options(
            joinedload(AssetAssignment.member).joinedload(Member.user),
            joinedload(AssetAssignment.providedByMember).joinedload(Member.user),
            joinedload(AssetAssignment.receivedByMember).joinedload(Member.user),
        )
        .order_by(AssetAssignment.providedDate.desc())
    )
    provisions = provisions_result.unique().scalars().all()
    active_provision = next((record for record in provisions if record.returnDate is None), None)

    scope = getattr(ctx, "scope", "organization")
    if scope == "self" and (active_provision is None or active_provision.memberId != ctx.member.id):
        raise HTTPException(status_code=404, detail="Asset not found")

    logs_result = await db.execute(
        select(AssetMaintenanceLog)
        .where(AssetMaintenanceLog.assetId == asset_id)
        .options(joinedload(AssetMaintenanceLog.loggedByMember).joinedload(Member.user))
        .order_by(AssetMaintenanceLog.createdAt.desc())
    )
    logs = logs_result.unique().scalars().all()

    units_result = await db.execute(
        select(AssetUnit).where(AssetUnit.assetId == asset_id)
    )
    units = units_result.scalars().all()

    unit_responses = [
        AssetUnitResponse(
            id=u.id,
            assetId=u.assetId,
            serialNumber=u.serialNumber,
            status=u.status,
            currentHolderMemberId=u.currentHolderMemberId,
            currentHolderName="",
            condition=u.condition,
        )
        for u in units
    ]

    base = _asset_summary(asset, active_provision)
    return AssetDetailResponse(
        **base.model_dump(),
        activeProvision=_provide_record_summary(active_provision) if active_provision else None,
        assetHistory=[_provide_record_summary(record) for record in provisions],
        maintenanceHistory=[_maintenance_summary(log) for log in logs],
        units=unit_responses,
    )


async def upsert_asset(
    db: AsyncSession,
    ctx: MemberContext,
    payload: AssetUpsertRequest,
    asset_id: str | None = None,
) -> AssetDetailResponse:
    is_new = asset_id is None
    if is_new:
        asset = Asset(id=generate_uuid(), organizationId=ctx.organization.id)
        db.add(asset)
    else:
        asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)

    duplicate_query = select(Asset).where(
        Asset.organizationId == ctx.organization.id,
        Asset.assetCode == payload.assetCode.strip(),
        Asset.deletedAt.is_(None),
    )
    if asset_id:
        duplicate_query = duplicate_query.where(Asset.id != asset_id)
    duplicate = (await db.execute(duplicate_query)).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Asset code already exists in this organization")

    # Check active provision via query to avoid lazy relationship access
    if not is_new:
        provision_result = await db.execute(
            select(AssetAssignment).where(
                AssetAssignment.assetId == asset.id,
                AssetAssignment.returnDate.is_(None),
            ).limit(1)
        )
        active_provision = provision_result.scalar_one_or_none()
    else:
        active_provision = None

    if active_provision is not None and payload.status != "PROVIDED":
        raise HTTPException(status_code=422, detail="Provided assets must be returned before changing their status")
    if active_provision is None and payload.status == "PROVIDED":
        raise HTTPException(status_code=422, detail="Use Provide Asset to mark an asset as provided")

    asset.assetCode = payload.assetCode.strip()
    asset.name = payload.name.strip()
    asset.categoryDefinitionId = payload.categoryDefinitionId

    # Derive category from definition if not provided explicitly
    if payload.category is not None:
        asset.category = payload.category
    elif payload.categoryDefinitionId:
        cat_result = await db.execute(
            select(AssetCategoryDefinition).where(
                AssetCategoryDefinition.id == payload.categoryDefinitionId,
                AssetCategoryDefinition.organizationId == ctx.organization.id,
            )
        )
        cat_def = cat_result.scalar_one_or_none()
        if cat_def:
            asset.category = cat_def.name.upper().replace(" ", "_")
        else:
            asset.category = "OTHER"
    else:
        asset.category = "OTHER"
    asset.serialNumber = payload.serialNumber.strip() if payload.serialNumber else None
    asset.model = payload.model.strip() if payload.model else None
    asset.purchaseDate = payload.purchaseDate
    asset.purchasePrice = payload.purchasePrice
    asset.warrantyExpiryDate = payload.warrantyExpiryDate
    asset.condition = payload.condition
    asset.status = payload.status
    asset.location = payload.location.strip() if payload.location else None
    asset.notes = payload.notes.strip() if payload.notes else None
    asset.quantity = payload.quantity

    # asset.id is set via generate_uuid() at creation — no flush needed

    # Handle custom fields
    if not is_new:
        result = await db.execute(
            select(AssetCustomFieldValue).where(
                AssetCustomFieldValue.assetId == asset.id
            )
        )
        existing_cfvs = result.scalars().all()
        incoming_cf_ids = {cf.fieldDefinitionId for cf in (payload.customFields or [])}
        for old in existing_cfvs:
            if old.fieldDefinitionId not in incoming_cf_ids:
                await db.delete(old)

    for cf in (payload.customFields or []):
        if not is_new:
            result = await db.execute(
                select(AssetCustomFieldValue).where(
                    AssetCustomFieldValue.assetId == asset.id,
                    AssetCustomFieldValue.fieldDefinitionId == cf.fieldDefinitionId,
                )
            )
            existing_cfv = result.scalar_one_or_none()
            if existing_cfv:
                existing_cfv.value = cf.value
                continue

        db.add(AssetCustomFieldValue(
            assetId=asset.id,
            fieldDefinitionId=cf.fieldDefinitionId,
            value=cf.value,
        ))

    # Handle units
    if not is_new:
        result = await db.execute(
            select(AssetUnit).where(AssetUnit.assetId == asset.id)
        )
        existing_units = result.scalars().all()
        existing_count = len(existing_units)
        for i, unit_input in enumerate(payload.units or []):
            if i < existing_count:
                existing_units[i].serialNumber = unit_input.serialNumber.strip() if unit_input.serialNumber else None
            else:
                db.add(AssetUnit(
                    assetId=asset.id,
                    serialNumber=unit_input.serialNumber.strip() if unit_input.serialNumber else None,
                    status="AVAILABLE",
                    condition=payload.condition,
                ))
        if len(payload.units or []) < existing_count:
            for unit in existing_units[len(payload.units or []):]:
                await db.delete(unit)
    else:
        for unit_input in (payload.units or []):
            db.add(AssetUnit(
                assetId=asset.id,
                serialNumber=unit_input.serialNumber.strip() if unit_input.serialNumber else None,
                status="AVAILABLE",
                condition=payload.condition,
            ))

    await db.commit()
    return await get_asset(db, ctx, asset.id)


async def delete_asset(db: AsyncSession, ctx: MemberContext, asset_id: str) -> None:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)
    active_provision = next((record for record in asset.provisions if record.returnDate is None), None)
    if active_provision is not None:
        raise HTTPException(status_code=422, detail="Return the provided asset before archiving it")
    asset.deletedAt = datetime.now(UTC)
    await db.commit()


# ── Unit-based Provide/Return ──────────────────────────────────────────────────


async def provide_asset(
    db: AsyncSession,
    ctx: MemberContext,
    asset_id: str,
    payload: AssetProvideRequest,
) -> AssetDetailResponse:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)
    if asset.status != "AVAILABLE":
        raise HTTPException(status_code=422, detail="Only available assets can be provided")
    if any(record.returnDate is None for record in asset.provisions if record.returnDate is None):
        raise HTTPException(status_code=422, detail="This asset is already provided")

    await _get_member_or_404(db, ctx.organization.id, payload.memberId)
    provider_id = payload.providedByMemberId or ctx.member.id
    await _get_member_or_404(db, ctx.organization.id, provider_id)

    # Find the specific unit to provide
    unit_to_provide: AssetUnit | None = None
    if payload.assetUnitId:
        unit_to_provide = next((u for u in (asset.units or []) if u.id == payload.assetUnitId), None)
        if unit_to_provide is None:
            raise HTTPException(status_code=422, detail="Asset unit not found")
        if unit_to_provide.status != "AVAILABLE":
            raise HTTPException(status_code=422, detail="This unit is not available for providing")
        unit_to_provide.status = "PROVIDED"
        unit_to_provide.currentHolderMemberId = payload.memberId
    else:
        # Legacy: provide entire asset (no units)
        pass

    db.add(
        AssetAssignment(
            assetId=asset.id,
            assetUnitId=payload.assetUnitId,
            memberId=payload.memberId,
            providedByMemberId=provider_id,
            providedDate=payload.providedDate or datetime.now(UTC),
            conditionWhileProviding=payload.conditionWhileProviding,
            provideNotes=payload.notes.strip() if payload.notes else None,
        )
    )

    # Recalculate status
    if unit_to_provide and (asset.units and len(asset.units) > 0):
        asset.status = _derive_asset_status(asset.units)
    else:
        asset.status = "PROVIDED"

    await db.commit()
    return await get_asset(db, ctx, asset.id)


async def return_asset(
    db: AsyncSession,
    ctx: MemberContext,
    asset_id: str,
    payload: AssetReturnRequest,
) -> AssetDetailResponse:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)

    # Filter provisions - if assetUnitId specified, match that specific unit
    provisions_pool = asset.provisions
    if payload.assetUnitId:
        provisions_pool = [p for p in provisions_pool if p.assetUnitId == payload.assetUnitId]

    provision = next((record for record in provisions_pool if record.returnDate is None), None)
    if provision is None:
        raise HTTPException(status_code=422, detail="This asset is not currently provided")
    if provision.memberId != payload.memberId:
        raise HTTPException(status_code=422, detail="The selected employee does not hold this asset")

    receiver_id = payload.receivedByMemberId or ctx.member.id
    await _get_member_or_404(db, ctx.organization.id, receiver_id)

    next_status = payload.nextStatus
    if next_status is None:
        next_status = "AVAILABLE" if payload.returnedCondition in {"NEW", "GOOD", "FAIR"} else "UNDER_MAINTENANCE"

    provision.returnDate = payload.returnDate or datetime.now(UTC)
    provision.returnedCondition = payload.returnedCondition
    provision.receivedByMemberId = receiver_id
    provision.returnNotes = payload.returnNotes.strip() if payload.returnNotes else None

    asset.condition = payload.returnedCondition

    # Update the specific unit
    if payload.assetUnitId:
        unit = next((u for u in (asset.units or []) if u.id == payload.assetUnitId), None)
        if unit:
            unit.status = next_status
            unit.condition = payload.returnedCondition
            unit.currentHolderMemberId = None

        if asset.units and len(asset.units) > 0:
            asset.status = _derive_asset_status(asset.units)
        else:
            asset.status = next_status
    else:
        asset.status = next_status

    await db.commit()
    return await get_asset(db, ctx, asset.id)


# ── Maintenance ────────────────────────────────────────────────────────────────


async def create_maintenance_record(
    db: AsyncSession,
    ctx: MemberContext,
    asset_id: str,
    payload: AssetMaintenanceCreateRequest,
) -> AssetDetailResponse:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)

    if payload.assetUnitId:
        unit = next((u for u in (asset.units or []) if u.id == payload.assetUnitId), None)
        if unit:
            unit.status = "UNDER_MAINTENANCE"

    db.add(
        AssetMaintenanceLog(
            assetId=asset.id,
            assetUnitId=payload.assetUnitId,
            loggedByMemberId=ctx.member.id,
            maintenanceType=payload.maintenanceType,
            issueDescription=payload.issueDescription.strip(),
            serviceDate=payload.serviceDate,
            expectedCompletionDate=payload.expectedCompletionDate,
            cost=payload.cost,
            status=payload.status,
            conditionBeforeMaintenance=payload.conditionBeforeMaintenance or asset.condition,
            notes=payload.notes.strip() if payload.notes else None,
        )
    )

    if asset.units and len(asset.units) > 0:
        asset.status = _derive_asset_status(asset.units)
    else:
        asset.status = "UNDER_MAINTENANCE"

    await db.commit()
    return await get_asset(db, ctx, asset.id)


async def update_maintenance_record(
    db: AsyncSession,
    ctx: MemberContext,
    asset_id: str,
    maintenance_id: str,
    payload: AssetMaintenanceUpdateRequest,
) -> AssetDetailResponse:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)
    log = await _get_maintenance_or_404(db, asset_id, maintenance_id)

    log.status = payload.status
    log.expectedCompletionDate = payload.expectedCompletionDate or log.expectedCompletionDate
    log.completedDate = payload.completedDate
    log.conditionAfterMaintenance = payload.conditionAfterMaintenance
    if payload.notes:
        log.notes = payload.notes.strip()

    if payload.status in {"OPEN", "IN_PROGRESS"}:
        if asset.units and len(asset.units) > 0:
            asset.status = _derive_asset_status(asset.units)
        else:
            asset.status = "UNDER_MAINTENANCE"
    elif payload.status == "COMPLETED":
        if payload.conditionAfterMaintenance:
            asset.condition = payload.conditionAfterMaintenance
        if payload.nextAssetStatus:
            if log.assetUnitId:
                unit = next((u for u in (asset.units or []) if u.id == log.assetUnitId), None)
                if unit:
                    unit.status = payload.nextAssetStatus
                    unit.condition = payload.conditionAfterMaintenance or unit.condition
                if asset.units and len(asset.units) > 0:
                    asset.status = _derive_asset_status(asset.units)
                else:
                    asset.status = payload.nextAssetStatus
            else:
                asset.status = payload.nextAssetStatus
    elif payload.status == "CANCELLED":
        if log.assetUnitId:
            unit = next((u for u in (asset.units or []) if u.id == log.assetUnitId), None)
            if unit:
                unit.status = payload.nextAssetStatus or "DAMAGED"
            if asset.units and len(asset.units) > 0:
                asset.status = _derive_asset_status(asset.units)
            else:
                asset.status = payload.nextAssetStatus or "DAMAGED"
        else:
            asset.status = payload.nextAssetStatus or "DAMAGED"

    await db.commit()
    return await get_asset(db, ctx, asset.id)


# ── Meta ───────────────────────────────────────────────────────────────────────


async def get_asset_meta(db: AsyncSession, ctx: MemberContext) -> AssetMetaResponse:
    scope = getattr(ctx, "scope", "organization")
    members_query = (
        select(Member.id, User.name, User.email)
        .join(User, User.id == Member.userId)
        .where(Member.organizationId == ctx.organization.id)
        .order_by(User.name.asc().nullslast(), User.email.asc())
    )
    if scope == "self":
        members_query = members_query.where(Member.id == ctx.member.id)
    result = await db.execute(members_query)
    members = [
        AssetLookupOption(id=member_id, label=name or email or member_id, email=email)
        for member_id, name, email in result.all()
    ]

    categories_result = await db.execute(
        select(AssetCategoryDefinition)
        .where(
            AssetCategoryDefinition.organizationId == ctx.organization.id,
            AssetCategoryDefinition.isActive.is_(True),
        )
        .options(joinedload(AssetCategoryDefinition.fields))
        .order_by(AssetCategoryDefinition.name.asc())
    )
    categories_raw = categories_result.unique().scalars().all()

    categories = [
        AssetCategoryResponse(
            id=c.id,
            name=c.name,
            isActive=c.isActive,
            fields=[
                CategoryFieldDefinitionResponse(
                    id=f.id,
                    categoryId=f.categoryId,
                    fieldName=f.fieldName,
                    fieldType=f.fieldType,
                    fieldOptions=f.fieldOptions,
                    isRequired=f.isRequired,
                    displayOrder=f.displayOrder,
                )
                for f in (c.fields or [])
            ],
        )
        for c in categories_raw
    ]

    return AssetMetaResponse(
        members=members,
        categories=categories,
        statuses=sorted(ASSET_STATUSES),
        conditions=sorted(ASSET_CONDITIONS),
        maintenanceTypes=sorted(MAINTENANCE_TYPES),
        maintenanceStatuses=sorted(MAINTENANCE_STATUSES),
        reportTypes=sorted(REPORT_TYPES),
    )


# ── Reports ────────────────────────────────────────────────────────────────────


async def export_asset_report(
    db: AsyncSession,
    ctx: MemberContext,
    request: AssetReportRequest,
) -> str:
    report_type = request.reportType

    if report_type in {"ALL_ASSETS", "AVAILABLE_ASSETS", "PROVIDED_ASSETS", "DAMAGED_ASSETS", "OFFBOARDING_PENDING_RETURN"}:
        status_filter = None
        if report_type == "AVAILABLE_ASSETS":
            status_filter = "AVAILABLE"
        elif report_type == "PROVIDED_ASSETS":
            status_filter = "PROVIDED"
        elif report_type == "DAMAGED_ASSETS":
            status_filter = "DAMAGED"
        elif report_type == "OFFBOARDING_PENDING_RETURN":
            status_filter = "PROVIDED"

        dataset = await list_assets(
            db,
            ctx,
            AssetFilters(
                status=status_filter,
                currentHolderMemberId=request.memberId,
                page=1,
                page_size=500,
            ),
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Asset Code",
                "Asset Name",
                "Category",
                "Status",
                "Condition",
                "Holder",
                "Location",
                "Units Total",
                "Units Available",
                "Units Provided",
            ]
        )
        for item in dataset.items:
            us = item.unitSummary
            writer.writerow(
                [
                    item.assetCode,
                    item.name,
                    item.category,
                    item.status,
                    item.condition,
                    item.currentHolderName or "",
                    item.location or "",
                    us.total if us else "",
                    us.available if us else "",
                    us.provided if us else "",
                ]
            )
        return buffer.getvalue()

    if report_type in {"RETURNED_ASSETS", "EMPLOYEE_ASSET_REPORT"}:
        query = (
            select(AssetAssignment)
            .join(Asset, Asset.id == AssetAssignment.assetId)
            .where(Asset.organizationId == ctx.organization.id, Asset.deletedAt.is_(None))
            .options(
                joinedload(AssetAssignment.asset),
                joinedload(AssetAssignment.member).joinedload(Member.user),
                joinedload(AssetAssignment.providedByMember).joinedload(Member.user),
                joinedload(AssetAssignment.receivedByMember).joinedload(Member.user),
            )
            .order_by(AssetAssignment.providedDate.desc())
        )
        if report_type == "RETURNED_ASSETS":
            query = query.where(AssetAssignment.returnDate.is_not(None))
        if request.memberId:
            query = query.where(AssetAssignment.memberId == request.memberId)
        rows = (await db.execute(query)).unique().scalars().all()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Asset Code",
                "Asset Name",
                "Employee",
                "Provided Date",
                "Return Date",
                "Returned Condition",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.asset.assetCode if row.asset else "",
                    row.asset.name if row.asset else "",
                    row.member.user.name if row.member and row.member.user else "",
                    row.providedDate.isoformat(),
                    row.returnDate.isoformat() if row.returnDate else "",
                    row.returnedCondition or "",
                ]
            )
        return buffer.getvalue()

    if report_type == "MAINTENANCE_HISTORY":
        rows = (
            await db.execute(
                select(AssetMaintenanceLog)
                .join(Asset, Asset.id == AssetMaintenanceLog.assetId)
                .where(Asset.organizationId == ctx.organization.id, Asset.deletedAt.is_(None))
                .options(joinedload(AssetMaintenanceLog.asset))
                .order_by(AssetMaintenanceLog.createdAt.desc())
            )
        ).unique().scalars().all()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "Asset Code",
                "Asset Name",
                "Maintenance Type",
                "Status",
                "Service Date",
                "Completed Date",
                "Cost",
                "Issue Description",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.asset.assetCode if row.asset else "",
                    row.asset.name if row.asset else "",
                    row.maintenanceType,
                    row.status,
                    row.serviceDate.isoformat(),
                    row.completedDate.isoformat() if row.completedDate else "",
                    f"{_to_float(row.cost):.2f}" if row.cost is not None else "",
                    row.issueDescription,
                ]
            )
        return buffer.getvalue()

    raise HTTPException(status_code=422, detail="Unsupported report type")


async def export_asset_report_pdf(
    db: AsyncSession,
    ctx: MemberContext,
    request: AssetReportRequest,
) -> bytes:
    csv_text = await export_asset_report(db, ctx, request)
    return _csv_to_pdf_bytes(request.reportType, csv_text)


# ── Dashboard ─────────────────────────────────────────────────────────────────


STATUS_COLORS: dict[str, str] = {
    "AVAILABLE": "#00874a",
    "PROVIDED": "#2563eb",
    "UNDER_MAINTENANCE": "#d97706",
    "DAMAGED": "#dc2626",
    "LOST": "#7c3aed",
    "RETIRED": "#6b7280",
    "DISPOSED": "#9ca3af",
}


async def get_dashboard(db: AsyncSession, ctx: MemberContext) -> AssetDashboardResponse:
    org_id = ctx.organization.id

    total = await db.scalar(
        select(func.count()).where(
            Asset.organizationId == org_id,
            Asset.deletedAt.is_(None),
        )
    )
    total = total or 0

    status_rows = await db.execute(
        select(Asset.status, func.count().label("cnt"))
        .where(Asset.organizationId == org_id, Asset.deletedAt.is_(None))
        .group_by(Asset.status)
    )
    status_map: dict[str, int] = dict(status_rows.all())

    def _c(name: str) -> int:
        return status_map.get(name, 0)

    raw_statuses = sorted(status_map.keys(), key=lambda s: -status_map[s])

    status_distribution = [
        AssetStatusCount(name=s, value=status_map[s], color=STATUS_COLORS.get(s, "#6b7280"))
        for s in raw_statuses
    ]

    monthly_rows = await db.execute(
        select(
            extract("year", Asset.createdAt).label("year"),
            extract("month", Asset.createdAt).label("month"),
            func.count().label("cnt"),
        )
        .where(Asset.organizationId == org_id, Asset.deletedAt.is_(None))
        .group_by(
            extract("year", Asset.createdAt),
            extract("month", Asset.createdAt),
        )
        .order_by(
            extract("year", Asset.createdAt).desc(),
            extract("month", Asset.createdAt).desc(),
        )
        .limit(12)
    )
    monthly_trends = [
        MonthlyTrend(month=f"{row.year}-{int(row.month):02d}", count=row.cnt)
        for row in monthly_rows
    ]
    monthly_trends.reverse()

    recent_activity: list[RecentActivityItem] = []

    provisions = await db.execute(
        select(AssetAssignment)
        .join(Asset, Asset.id == AssetAssignment.assetId)
        .where(
            Asset.organizationId == org_id,
            Asset.deletedAt.is_(None),
        )
        .options(
            joinedload(AssetAssignment.asset),
            joinedload(AssetAssignment.member).joinedload(Member.user),
        )
        .order_by(AssetAssignment.providedDate.desc())
        .limit(5)
    )
    for p in provisions.unique().scalars().all():
        recent_activity.append(RecentActivityItem(
            type="PROVIDED",
            assetName=p.asset.name if p.asset else "",
            memberName=p.member.user.name if p.member and p.member.user else None,
            date=p.providedDate.isoformat() if p.providedDate else "",
            detail=p.provideNotes.strip() if p.provideNotes else None,
        ))

    returns = await db.execute(
        select(AssetAssignment)
        .join(Asset, Asset.id == AssetAssignment.assetId)
        .where(
            Asset.organizationId == org_id,
            Asset.deletedAt.is_(None),
            AssetAssignment.returnDate.is_not(None),
        )
        .options(
            joinedload(AssetAssignment.asset),
            joinedload(AssetAssignment.member).joinedload(Member.user),
        )
        .order_by(AssetAssignment.returnDate.desc())
        .limit(5)
    )
    for r in returns.unique().scalars().all():
        recent_activity.append(RecentActivityItem(
            type="RETURNED",
            assetName=r.asset.name if r.asset else "",
            memberName=r.member.user.name if r.member and r.member.user else None,
            date=r.returnDate.isoformat() if r.returnDate else "",
            detail=r.returnNotes.strip() if r.returnNotes else None,
        ))

    maintenance = await db.execute(
        select(AssetMaintenanceLog)
        .join(Asset, Asset.id == AssetMaintenanceLog.assetId)
        .where(
            Asset.organizationId == org_id,
            Asset.deletedAt.is_(None),
        )
        .options(
            joinedload(AssetMaintenanceLog.asset),
        )
        .order_by(AssetMaintenanceLog.createdAt.desc())
        .limit(5)
    )
    for m in maintenance.unique().scalars().all():
        recent_activity.append(RecentActivityItem(
            type="MAINTENANCE",
            assetName=m.asset.name if m.asset else "",
            memberName=None,
            date=m.createdAt.isoformat() if m.createdAt else "",
            detail=m.issueDescription.strip() if m.issueDescription else None,
        ))

    recent_activity.sort(key=lambda x: x.date, reverse=True)
    recent_activity = recent_activity[:8]

    open_tickets_result = await db.execute(
        select(AssetMaintenanceLog)
        .join(Asset, Asset.id == AssetMaintenanceLog.assetId)
        .where(
            Asset.organizationId == org_id,
            Asset.deletedAt.is_(None),
            AssetMaintenanceLog.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .options(
            joinedload(AssetMaintenanceLog.asset),
        )
        .order_by(AssetMaintenanceLog.createdAt.desc())
        .limit(5)
    )
    open_tickets = open_tickets_result.unique().scalars().all()

    recent_tickets = [
        TicketAlertItem(
            id=t.id,
            assetName=t.asset.name if t.asset else "",
            maintenanceType=t.maintenanceType,
            status=t.status,
            issueDescription=t.issueDescription.strip() if t.issueDescription else "",
            createdAt=t.createdAt.isoformat() if t.createdAt else "",
        )
        for t in open_tickets
    ]

    return AssetDashboardResponse(
        totalAssets=total,
        availableCount=_c("AVAILABLE"),
        providedCount=_c("PROVIDED"),
        maintenanceCount=_c("UNDER_MAINTENANCE"),
        damagedCount=_c("DAMAGED"),
        retiredCount=_c("RETIRED"),
        openTicketCount=len(open_tickets),
        statusDistribution=status_distribution,
        monthlyTrends=monthly_trends,
        recentActivity=recent_activity,
        recentTickets=recent_tickets,
    )
