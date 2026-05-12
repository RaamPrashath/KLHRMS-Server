from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.asset import Asset
from app.models.asset_assignment import AssetAssignment
from app.models.asset_maintenance_log import AssetMaintenanceLog
from app.models.member import Member
from app.models.user import User
from app.modules.assets.schema import (
    ASSET_CATEGORIES,
    ASSET_CONDITIONS,
    ASSET_STATUSES,
    MAINTENANCE_STATUSES,
    MAINTENANCE_TYPES,
    REPORT_TYPES,
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
    AssetSummary,
    AssetUpsertRequest,
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
        .options(joinedload(Asset.provisions), joinedload(Asset.maintenanceLogs))
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
    return AssetSummary(
        id=asset.id,
        assetCode=asset.assetCode,
        name=asset.name,
        category=asset.category,
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
    )


def _provide_record_summary(record: AssetAssignment) -> AssetProvideRecordSummary:
    holder = record.member.user if record.member and record.member.user else None
    provider = record.providedByMember.user if record.providedByMember and record.providedByMember.user else None
    receiver = record.receivedByMember.user if record.receivedByMember and record.receivedByMember.user else None
    return AssetProvideRecordSummary(
        id=record.id,
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
    if filters.status:
        query = query.where(Asset.status == filters.status)

    total_result = await db.execute(select(func.count()).select_from(query.order_by(None).subquery()))
    total = total_result.scalar_one()

    rows = await db.execute(
        query.offset((filters.page - 1) * filters.page_size)
        .limit(filters.page_size)
        .options(joinedload(Asset.provisions), joinedload(Asset.maintenanceLogs))
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

    base = _asset_summary(asset, active_provision)
    return AssetDetailResponse(
        **base.model_dump(),
        activeProvision=_provide_record_summary(active_provision) if active_provision else None,
        assetHistory=[_provide_record_summary(record) for record in provisions],
        maintenanceHistory=[_maintenance_summary(log) for log in logs],
    )


async def upsert_asset(
    db: AsyncSession,
    ctx: MemberContext,
    payload: AssetUpsertRequest,
    asset_id: str | None = None,
) -> AssetDetailResponse:
    asset: Asset | None = None
    if asset_id:
        asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)
    else:
        asset = Asset(organizationId=ctx.organization.id)
        db.add(asset)

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

    active_provision = next((record for record in asset.provisions if record.returnDate is None), None)
    if active_provision is not None and payload.status != "PROVIDED":
        raise HTTPException(status_code=422, detail="Provided assets must be returned before changing their status")
    if active_provision is None and payload.status == "PROVIDED":
        raise HTTPException(status_code=422, detail="Use Provide Asset to mark an asset as provided")

    asset.assetCode = payload.assetCode.strip()
    asset.name = payload.name.strip()
    asset.category = payload.category
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

    await db.commit()
    return await get_asset(db, ctx, asset.id)


async def delete_asset(db: AsyncSession, ctx: MemberContext, asset_id: str) -> None:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)
    active_provision = next((record for record in asset.provisions if record.returnDate is None), None)
    if active_provision is not None:
        raise HTTPException(status_code=422, detail="Return the provided asset before archiving it")
    asset.deletedAt = datetime.now(UTC)
    await db.commit()


async def provide_asset(
    db: AsyncSession,
    ctx: MemberContext,
    asset_id: str,
    payload: AssetProvideRequest,
) -> AssetDetailResponse:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)
    if asset.status != "AVAILABLE":
        raise HTTPException(status_code=422, detail="Only available assets can be provided")
    if any(record.returnDate is None for record in asset.provisions):
        raise HTTPException(status_code=422, detail="This asset is already provided")

    await _get_member_or_404(db, ctx.organization.id, payload.memberId)
    provider_id = payload.providedByMemberId or ctx.member.id
    await _get_member_or_404(db, ctx.organization.id, provider_id)

    db.add(
        AssetAssignment(
            assetId=asset.id,
            memberId=payload.memberId,
            providedByMemberId=provider_id,
            providedDate=payload.providedDate or datetime.now(UTC),
            conditionWhileProviding=payload.conditionWhileProviding,
            provideNotes=payload.notes.strip() if payload.notes else None,
        )
    )
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
    provision = next((record for record in asset.provisions if record.returnDate is None), None)
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
    asset.status = next_status

    await db.commit()
    return await get_asset(db, ctx, asset.id)


async def create_maintenance_record(
    db: AsyncSession,
    ctx: MemberContext,
    asset_id: str,
    payload: AssetMaintenanceCreateRequest,
) -> AssetDetailResponse:
    asset = await _get_asset_or_404(db, ctx.organization.id, asset_id)
    db.add(
        AssetMaintenanceLog(
            assetId=asset.id,
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
        asset.status = "UNDER_MAINTENANCE"
    elif payload.status == "COMPLETED":
        if payload.conditionAfterMaintenance:
            asset.condition = payload.conditionAfterMaintenance
        if payload.nextAssetStatus:
            asset.status = payload.nextAssetStatus
    elif payload.status == "CANCELLED":
        asset.status = payload.nextAssetStatus or "DAMAGED"

    await db.commit()
    return await get_asset(db, ctx, asset.id)


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
    return AssetMetaResponse(
        members=members,
        categories=sorted(ASSET_CATEGORIES),
        statuses=sorted(ASSET_STATUSES),
        conditions=sorted(ASSET_CONDITIONS),
        maintenanceTypes=sorted(MAINTENANCE_TYPES),
        maintenanceStatuses=sorted(MAINTENANCE_STATUSES),
        reportTypes=sorted(REPORT_TYPES),
    )


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
            ]
        )
        for item in dataset.items:
            writer.writerow(
                [
                    item.assetCode,
                    item.name,
                    item.category,
                    item.status,
                    item.condition,
                    item.currentHolderName or "",
                    item.location or "",
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
