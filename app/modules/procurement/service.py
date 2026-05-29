from __future__ import annotations

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.asset import Asset
from app.models.asset_category_definition import AssetCategoryDefinition
from app.models.asset_maintenance_log import AssetMaintenanceLog
from app.models.asset_purchase_order import AssetPurchaseOrder
from app.models.asset_purchase_requisition import (
    AssetPurchaseRequisition,
    AssetPurchaseRequisitionActivityLog,
)
from app.models.asset_unit import AssetUnit
from app.models.department import Department
from app.models.member import Member
from app.models.organization import Organization
from app.models.role import Role
from app.modules.assets.service import _members_with_asset_admin_scope
from app.modules.procurement.schema import (
    AssetPurchaseRequisitionCreateRequest,
    AssetPurchaseRequisitionListResponse,
    AssetPurchaseRequisitionRead,
    ProcurementAdminRecipientOption,
    ProcurementAdminRecipientsResponse,
    ProcurementActivityEntry,
    ProcurementCategoryOption,
    ProcurementDecisionRequest,
    ProcurementDepartmentOption,
    ProcurementMetaResponse,
    ProcurementPurchaseOrderCreateRequest,
    ProcurementPurchaseOrderRead,
    ProcurementReplacementTicketOption,
    ProcurementSnapshotRead,
)
from app.integrations.storage.supabase_storage import (
    SupabaseStorageError,
    upload_private_file,
)
from app.shared.deps.organization_member import MemberContext
from app.shared.notifications.email import (
    send_procurement_purchase_order,
    send_procurement_requisition_decided,
    send_procurement_requisition_submitted,
)
from app.shared.config import get_settings
from app.shared.utils.permissions import get_permission_scope


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _normalize_subject(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _is_return_request(subject: str | None) -> bool:
    return _normalize_subject(subject) == "asset return request"


def _derive_warranty_status(
    purchase_date: date | None,
    warranty_expiry_date: date | None,
) -> str:
    del purchase_date
    if warranty_expiry_date is None:
        return "UNKNOWN"
    return "EXPIRED" if warranty_expiry_date < date.today() else "IN_WARRANTY"


def _member_display_name(member: Member | None) -> str | None:
    if member is None or member.user is None:
        return None
    return member.user.name or member.user.email


def _can_view_requisition(
    requisition: AssetPurchaseRequisition,
    actor_member_id: str,
    scope: str,
) -> bool:
    if scope == "self":
        return requisition.raisedByMemberId == actor_member_id
    return True


def _is_finance_manager(member: Member | None) -> bool:
    return bool(member and member.role and (member.role.name or "").strip().lower() == "finance manager")


def _can_finance_approve(
    requisition: AssetPurchaseRequisition,
    actor: Member,
) -> bool:
    if requisition.status != "PENDING_FINANCE_APPROVAL":
        return False
    return _is_finance_manager(actor) and get_permission_scope(actor.role.permissions, "procurement", "approve") == "organization"  # type: ignore[union-attr]


async def _get_org_finance_approvers(db: AsyncSession, organization_id: str) -> list[Member]:
    result = await db.execute(
        select(Member)
        .options(joinedload(Member.role), joinedload(Member.user))
        .where(Member.organizationId == organization_id)
    )
    members = result.unique().scalars().all()
    return [
        member
        for member in members
        if _is_finance_manager(member)
        and member.role is not None
        and get_permission_scope(member.role.permissions, "procurement", "approve") == "organization"
    ]


def _can_issue_purchase_order(requisition: AssetPurchaseRequisition, actor: Member) -> bool:
    if requisition.status != "APPROVED" or actor.role is None:
        return False
    return get_permission_scope(actor.role.permissions, "procurement", "approve") == "organization"


def _should_receive_procurement_po(role: Role | None) -> bool:
    if role is None:
        return False

    permissions = role.permissions or {}
    organization_permissions = permissions.get("organization") or {}
    permission_permissions = permissions.get("permission") or {}
    procurement_permissions = permissions.get("procurement") or {}

    if organization_permissions.get("view") == "organization":
        return True
    if permission_permissions.get("view") == "organization":
        return True
    if procurement_permissions.get("view") == "organization":
        return True
    return "admin" in (role.name or "").strip().lower()


async def _get_procurement_admin_recipients(
    db: AsyncSession, organization_id: str
) -> list[Member]:
    asset_admin_members = await _members_with_asset_admin_scope(db, organization_id)
    asset_admin_ids = {member.id for member in asset_admin_members}

    result = await db.execute(
        select(Member)
        .options(joinedload(Member.user), joinedload(Member.role))
        .where(Member.organizationId == organization_id, Member.status == "ACTIVE")
    )
    members = result.unique().scalars().all()
    recipients: list[Member] = []
    for member in members:
        if member.user is None or not member.user.email:
            continue
        if member.id in asset_admin_ids or _should_receive_procurement_po(member.role):
            recipients.append(member)

    recipients.sort(
        key=lambda member: (
            (member.user.name or member.user.email or "").lower(),
            (member.user.email or "").lower(),
        )
    )
    return recipients


async def _get_org(db: AsyncSession, organization_id: str) -> Organization | None:
    result = await db.execute(select(Organization).where(Organization.id == organization_id))
    return result.scalar_one_or_none()


async def _next_request_number(db: AsyncSession, organization_id: str) -> int:
    result = await db.execute(
        select(func.max(AssetPurchaseRequisition.requestNumber)).where(
            AssetPurchaseRequisition.organizationId == organization_id
        )
    )
    current = result.scalar()
    return (current or 0) + 1


async def _load_requisition(
    db: AsyncSession,
    organization_id: str,
    requisition_id: str,
) -> AssetPurchaseRequisition | None:
    result = await db.execute(
        select(AssetPurchaseRequisition)
        .options(
            joinedload(AssetPurchaseRequisition.raisedBy).joinedload(Member.user),
            joinedload(AssetPurchaseRequisition.raisedBy).joinedload(Member.role),
            joinedload(AssetPurchaseRequisition.approvedBy).joinedload(Member.user),
            joinedload(AssetPurchaseRequisition.affectedEmployee).joinedload(Member.user),
            joinedload(AssetPurchaseRequisition.department),
            joinedload(AssetPurchaseRequisition.categoryDefinition),
            selectinload(AssetPurchaseRequisition.activityLogs)
            .joinedload(AssetPurchaseRequisitionActivityLog.actor)
            .joinedload(Member.user),
            selectinload(AssetPurchaseRequisition.purchaseOrders)
            .joinedload(AssetPurchaseOrder.recipient)
            .joinedload(Member.user),
            selectinload(AssetPurchaseRequisition.purchaseOrders)
            .joinedload(AssetPurchaseOrder.generatedBy)
            .joinedload(Member.user),
        )
        .where(
            AssetPurchaseRequisition.organizationId == organization_id,
            AssetPurchaseRequisition.id == requisition_id,
        )
    )
    return result.unique().scalar_one_or_none()


def _serialize_snapshot(data: dict[str, Any] | None) -> ProcurementSnapshotRead | None:
    if not data:
        return None
    return ProcurementSnapshotRead(**data)


def _serialize_requisition(
    requisition: AssetPurchaseRequisition,
    actor: Member,
) -> AssetPurchaseRequisitionRead:
    activities = [
        ProcurementActivityEntry(
            id=entry.id,
            actorId=entry.actorId,
            actorName=_member_display_name(entry.actor),
            action=entry.action,
            comment=entry.comment,
            createdAt=entry.createdAt,
        )
        for entry in requisition.activityLogs or []
    ]
    purchase_orders = [
        ProcurementPurchaseOrderRead(
            id=entry.id,
            poNumber=entry.poNumber,
            formatKey=entry.formatKey,
            status=entry.status,
            storageBucket=entry.storageBucket,
            storagePath=entry.storagePath,
            fileName=entry.fileName,
            recipientMemberId=entry.recipientMemberId,
            recipientName=_member_display_name(entry.recipient),
            recipientEmail=entry.recipientEmail,
            generatedByMemberId=entry.generatedByMemberId,
            generatedByName=_member_display_name(entry.generatedBy),
            generatedAt=entry.generatedAt,
            sentAt=entry.sentAt,
            emailSubject=entry.emailSubject,
            emailError=entry.emailError,
            createdAt=entry.createdAt,
            updatedAt=entry.updatedAt,
        )
        for entry in requisition.purchaseOrders or []
    ]
    return AssetPurchaseRequisitionRead(
        id=requisition.id,
        requestType=requisition.requestType,
        status=requisition.status,
        requestNumber=requisition.requestNumber,
        requestLabel=f"APR-{requisition.requestNumber:05d}" if requisition.requestNumber else None,
        raisedByMemberId=requisition.raisedByMemberId,
        raisedByName=_member_display_name(requisition.raisedBy),
        approvedByMemberId=requisition.approvedByMemberId,
        approvedByName=_member_display_name(requisition.approvedBy),
        approvedAt=requisition.approvedAt,
        rejectedAt=requisition.rejectedAt,
        reviewerComment=requisition.reviewerComment,
        justification=requisition.justification,
        requiredByDate=requisition.requiredByDate,
        estimatedUnitCost=_to_float(requisition.estimatedUnitCost),
        estimatedQuantity=requisition.estimatedQuantity,
        estimatedTotalCost=_to_float(requisition.estimatedTotalCost),
        vendorPreference=requisition.vendorPreference,
        urgency=requisition.urgency,
        costCenterOrDepartmentId=requisition.costCenterOrDepartmentId,
        costCenterOrDepartmentName=requisition.department.name if requisition.department else None,
        assetName=requisition.assetName,
        assetCode=requisition.assetCode,
        categoryDefinitionId=requisition.categoryDefinitionId,
        categoryName=requisition.categoryDefinition.name if requisition.categoryDefinition else None,
        specificationNotes=requisition.specificationNotes,
        maintenanceTicketId=requisition.maintenanceTicketId,
        assetId=requisition.assetId,
        assetUnitId=requisition.assetUnitId,
        affectedEmployeeId=requisition.affectedEmployeeId,
        affectedEmployeeName=_member_display_name(requisition.affectedEmployee),
        originalPurchaseDate=requisition.originalPurchaseDate,
        warrantyExpiryDate=requisition.warrantyExpiryDate,
        warrantyStatus=requisition.warrantyStatus,
        replacementReason=requisition.replacementReason,
        replacementMode=requisition.replacementMode,
        ticketSnapshot=_serialize_snapshot(requisition.ticketSnapshot),
        assetSnapshot=_serialize_snapshot(requisition.assetSnapshot),
        createdAt=requisition.createdAt,
        updatedAt=requisition.updatedAt,
        currentUserCanApprove=_can_finance_approve(requisition, actor),
        canSubmit=requisition.status == "DRAFT" and requisition.raisedByMemberId == actor.id,
        approvalsPendingFinance=requisition.status == "PENDING_FINANCE_APPROVAL",
        activities=activities,
        purchaseOrders=purchase_orders,
    )


async def _log_activity(
    db: AsyncSession,
    organization_id: str,
    requisition_id: str,
    actor_id: str | None,
    action: str,
    comment: str | None = None,
) -> None:
    db.add(
        AssetPurchaseRequisitionActivityLog(
            organizationId=organization_id,
            requisitionId=requisition_id,
            actorId=actor_id,
            action=action,
            comment=comment,
        )
    )
    await db.flush()


async def _next_purchase_order_number(db: AsyncSession, organization_id: str) -> int:
    result = await db.execute(
        select(func.count(AssetPurchaseOrder.id)).where(AssetPurchaseOrder.organizationId == organization_id)
    )
    current = result.scalar() or 0
    return current + 1


def _purchase_order_number(sequence: int) -> str:
    return f"PO-{datetime.now(UTC).year}-{sequence:05d}"


def _wrap_pdf_text(
    pdf: canvas.Canvas,
    text: str,
    *,
    font_name: str,
    font_size: int,
    max_width: float,
) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
    lines.append(current)
    return lines


def _draw_pdf_label_value(
    pdf: canvas.Canvas,
    *,
    x: float,
    y: float,
    label: str,
    value: str,
    width: float,
) -> float:
    pdf.setFillColor(colors.HexColor("#6E6E73"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(x, y, label)

    lines = _wrap_pdf_text(
        pdf,
        value,
        font_name="Helvetica-Bold",
        font_size=11,
        max_width=width,
    )
    cursor = y - 14
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 11)
    for line in lines:
        pdf.drawString(x, cursor, line)
        cursor -= 14
    return cursor


def _render_purchase_order_pdf(
    requisition: AssetPurchaseRequisition,
    *,
    po_number: str,
    organization_name: str,
    recipient_name: str,
    generated_by_name: str,
) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    content_width = width - (margin * 2)
    y = height - margin

    pdf.setTitle(f"{po_number}.pdf")
    pdf.setStrokeColor(colors.HexColor("#E5E5EA"))
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(margin, y, "Purchase Order")
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.HexColor("#6E6E73"))
    pdf.drawRightString(width - margin, y, organization_name)
    y -= 16
    pdf.drawRightString(width - margin, y, "KL HRMS Procurement")
    y -= 22
    pdf.line(margin, y, width - margin, y)
    y -= 22

    left_x = margin
    right_x = margin + (content_width / 2) + 10
    column_width = (content_width / 2) - 10

    left_bottom = _draw_pdf_label_value(
        pdf, x=left_x, y=y, label="PO Number", value=po_number, width=column_width
    )
    right_bottom = _draw_pdf_label_value(
        pdf,
        x=right_x,
        y=y,
        label="Requisition",
        value=f"APR-{requisition.requestNumber:05d}" if requisition.requestNumber else requisition.id,
        width=column_width,
    )
    y = min(left_bottom, right_bottom) - 10

    left_bottom = _draw_pdf_label_value(
        pdf,
        x=left_x,
        y=y,
        label="Recipient",
        value=recipient_name,
        width=column_width,
    )
    right_bottom = _draw_pdf_label_value(
        pdf,
        x=right_x,
        y=y,
        label="Prepared By",
        value=generated_by_name,
        width=column_width,
    )
    y = min(left_bottom, right_bottom) - 10

    left_bottom = _draw_pdf_label_value(
        pdf,
        x=left_x,
        y=y,
        label="Asset / Item",
        value=requisition.assetName or requisition.requestType.title(),
        width=column_width,
    )
    right_bottom = _draw_pdf_label_value(
        pdf,
        x=right_x,
        y=y,
        label="Preferred Vendor",
        value=requisition.vendorPreference or "Not specified",
        width=column_width,
    )
    y = min(left_bottom, right_bottom) - 16

    pdf.roundRect(margin, y - 90, content_width, 90, 12, stroke=1, fill=0)
    table_y = y - 18
    pdf.setFillColor(colors.HexColor("#6E6E73"))
    pdf.setFont("Helvetica", 9)
    headers = ["Description", "Qty", "Unit Cost", "Total Cost"]
    header_positions = [margin + 12, margin + 260, margin + 340, margin + 430]
    for header, x_pos in zip(headers, header_positions, strict=False):
        pdf.drawString(x_pos, table_y, header)

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 11)
    row_y = table_y - 20
    pdf.drawString(margin + 12, row_y, (requisition.assetName or "Asset Purchase")[:38])
    pdf.drawString(margin + 260, row_y, str(requisition.estimatedQuantity or 1))
    pdf.drawString(margin + 340, row_y, f"INR {(_to_float(requisition.estimatedUnitCost) or 0):,.2f}")
    pdf.drawString(margin + 430, row_y, f"INR {(_to_float(requisition.estimatedTotalCost) or 0):,.2f}")
    y -= 112

    pdf.setFillColor(colors.HexColor("#6E6E73"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, y, "Justification")
    y -= 14
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 10)
    for line in _wrap_pdf_text(
        pdf,
        requisition.justification,
        font_name="Helvetica",
        font_size=10,
        max_width=content_width,
    ):
        pdf.drawString(margin, y, line)
        y -= 13

    if requisition.specificationNotes:
        y -= 8
        pdf.setFillColor(colors.HexColor("#6E6E73"))
        pdf.setFont("Helvetica", 9)
        pdf.drawString(margin, y, "Specifications / Notes")
        y -= 14
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica", 10)
        for line in _wrap_pdf_text(
            pdf,
            requisition.specificationNotes,
            font_name="Helvetica",
            font_size=10,
            max_width=content_width,
        ):
            pdf.drawString(margin, y, line)
            y -= 13

    y -= 16
    pdf.setStrokeColor(colors.HexColor("#E5E5EA"))
    pdf.line(margin, y, width - margin, y)
    y -= 18
    pdf.setFillColor(colors.HexColor("#6E6E73"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, y, f"Approved by Finance on {requisition.approvedAt.date().isoformat() if requisition.approvedAt else date.today().isoformat()}")
    if requisition.requiredByDate:
        pdf.drawRightString(width - margin, y, f"Required by {requisition.requiredByDate.isoformat()}")

    pdf.save()
    return buffer.getvalue()


async def _get_replacement_ticket_context(
    db: AsyncSession,
    organization_id: str,
    maintenance_id: str,
) -> tuple[AssetMaintenanceLog, dict[str, Any], dict[str, Any]]:
    result = await db.execute(
        select(AssetMaintenanceLog)
        .options(
            joinedload(AssetMaintenanceLog.asset).joinedload(Asset.customFieldValues),
            joinedload(AssetMaintenanceLog.loggedByMember).joinedload(Member.user),
        )
        .where(
            AssetMaintenanceLog.organizationId == organization_id,
            AssetMaintenanceLog.id == maintenance_id,
        )
    )
    ticket = result.unique().scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Replacement ticket not found")
    if ticket.assetId is None or _is_return_request(ticket.subject):
        raise HTTPException(status_code=400, detail="Selected ticket is not eligible for replacement purchasing")
    if ticket.status not in {"OPEN", "IN_PROGRESS"}:
        raise HTTPException(status_code=400, detail="Only open maintenance tickets can be used for replacement purchasing")

    asset = ticket.asset
    if asset is None:
        raise HTTPException(status_code=400, detail="Replacement ticket has no linked asset")

    unit: AssetUnit | None = None
    if ticket.assetUnitId:
        unit_result = await db.execute(
            select(AssetUnit).where(AssetUnit.id == ticket.assetUnitId)
        )
        unit = unit_result.scalar_one_or_none()

    affected_member: Member | None = None
    affected_member_id = unit.currentHolderMemberId if unit else None
    if affected_member_id:
        member_result = await db.execute(
            select(Member)
            .options(joinedload(Member.user))
            .where(
                Member.organizationId == organization_id,
                Member.id == affected_member_id,
            )
        )
        affected_member = member_result.unique().scalar_one_or_none()

    warranty_status = _derive_warranty_status(asset.purchaseDate, asset.warrantyExpiryDate)
    ticket_snapshot = {
        "ticketId": ticket.ticketId,
        "subject": ticket.subject,
        "issueDescription": ticket.issueDescription,
        "status": ticket.status,
        "createdAt": ticket.createdAt.isoformat(),
        "serviceDate": ticket.serviceDate.isoformat(),
        "maintenanceType": ticket.maintenanceType,
        "assetName": asset.name,
        "assetCode": asset.assetCode,
        "serialNumber": unit.serialNumber if unit else asset.serialNumber,
        "affectedEmployeeName": _member_display_name(affected_member),
        "raisedByName": _member_display_name(ticket.loggedByMember),
        "currentCondition": unit.condition if unit else asset.condition,
        "originalPurchaseDate": asset.purchaseDate.isoformat() if asset.purchaseDate else None,
        "warrantyExpiryDate": asset.warrantyExpiryDate.isoformat() if asset.warrantyExpiryDate else None,
        "warrantyStatus": warranty_status,
        "replacementMode": ticket.replacementDecision,
    }
    asset_snapshot = {
        "assetName": asset.name,
        "assetCode": asset.assetCode,
        "serialNumber": unit.serialNumber if unit else asset.serialNumber,
        "currentCondition": unit.condition if unit else asset.condition,
        "originalPurchaseDate": asset.purchaseDate.isoformat() if asset.purchaseDate else None,
        "warrantyExpiryDate": asset.warrantyExpiryDate.isoformat() if asset.warrantyExpiryDate else None,
        "warrantyStatus": warranty_status,
    }
    return ticket, ticket_snapshot, asset_snapshot


async def get_procurement_meta(
    db: AsyncSession,
    ctx: MemberContext,
) -> ProcurementMetaResponse:
    departments_result = await db.execute(
        select(Department)
        .where(Department.organizationId == ctx.organization.id)
        .order_by(Department.name.asc())
    )
    categories_result = await db.execute(
        select(AssetCategoryDefinition)
        .where(
            AssetCategoryDefinition.organizationId == ctx.organization.id,
            AssetCategoryDefinition.isActive.is_(True),
        )
        .order_by(AssetCategoryDefinition.name.asc())
    )
    tickets_result = await db.execute(
        select(AssetMaintenanceLog)
        .options(
            joinedload(AssetMaintenanceLog.asset),
            joinedload(AssetMaintenanceLog.loggedByMember).joinedload(Member.user),
        )
        .where(
            AssetMaintenanceLog.organizationId == ctx.organization.id,
            AssetMaintenanceLog.ticketMode == "ASSET_ISSUE",
            AssetMaintenanceLog.assetId.is_not(None),
            AssetMaintenanceLog.status.in_(["OPEN", "IN_PROGRESS"]),
        )
        .order_by(AssetMaintenanceLog.createdAt.desc())
    )
    tickets = [ticket for ticket in tickets_result.unique().scalars().all() if not _is_return_request(ticket.subject)]

    unit_ids = {ticket.assetUnitId for ticket in tickets if ticket.assetUnitId}
    units_by_id: dict[str, AssetUnit] = {}
    if unit_ids:
        unit_result = await db.execute(select(AssetUnit).where(AssetUnit.id.in_(unit_ids)))
        units_by_id = {unit.id: unit for unit in unit_result.scalars().all()}

    affected_member_ids = {
        unit.currentHolderMemberId for unit in units_by_id.values() if unit.currentHolderMemberId
    }
    affected_members: dict[str, Member] = {}
    if affected_member_ids:
        affected_result = await db.execute(
            select(Member)
            .options(joinedload(Member.user))
            .where(
                Member.organizationId == ctx.organization.id,
                Member.id.in_(affected_member_ids),
            )
        )
        affected_members = {member.id: member for member in affected_result.unique().scalars().all()}

    replacement_tickets: list[ProcurementReplacementTicketOption] = []
    for ticket in tickets:
        asset = ticket.asset
        if asset is None:
            continue
        unit = units_by_id.get(ticket.assetUnitId) if ticket.assetUnitId else None
        affected_member = affected_members.get(unit.currentHolderMemberId) if unit and unit.currentHolderMemberId else None
        warranty_status = _derive_warranty_status(asset.purchaseDate, asset.warrantyExpiryDate)
        replacement_tickets.append(
            ProcurementReplacementTicketOption(
                id=ticket.id,
                ticketId=ticket.ticketId,
                subject=ticket.subject,
                issueDescription=ticket.issueDescription,
                status=ticket.status,
                serviceDate=ticket.serviceDate.isoformat(),
                maintenanceType=ticket.maintenanceType,
                assetId=ticket.assetId,
                assetUnitId=ticket.assetUnitId,
                assetName=asset.name,
                assetCode=asset.assetCode,
                serialNumber=unit.serialNumber if unit else asset.serialNumber,
                currentCondition=unit.condition if unit else asset.condition,
                originalPurchaseDate=asset.purchaseDate.isoformat() if asset.purchaseDate else None,
                warrantyExpiryDate=asset.warrantyExpiryDate.isoformat() if asset.warrantyExpiryDate else None,
                warrantyStatus=warranty_status,
                affectedEmployeeId=affected_member.id if affected_member else None,
                affectedEmployeeName=_member_display_name(affected_member),
                raisedByName=_member_display_name(ticket.loggedByMember),
                replacementMode=ticket.replacementDecision,
                createdAt=ticket.createdAt.isoformat(),
            )
        )

    return ProcurementMetaResponse(
        departments=[
            ProcurementDepartmentOption(id=department.id, name=department.name)
            for department in departments_result.scalars().all()
        ],
        categories=[
            ProcurementCategoryOption(
                id=category.id,
                name=category.name,
                assetCode=category.assetCode,
            )
            for category in categories_result.scalars().all()
        ],
        replacementTickets=replacement_tickets,
    )


async def get_procurement_admin_recipients(
    db: AsyncSession,
    ctx: MemberContext,
) -> ProcurementAdminRecipientsResponse:
    if ctx.member.role is None or get_permission_scope(ctx.member.role.permissions, "procurement", "approve") != "organization":
        raise HTTPException(status_code=403, detail="Only procurement approvers can access admin recipients")

    recipients = await _get_procurement_admin_recipients(db, ctx.organization.id)
    return ProcurementAdminRecipientsResponse(
        items=[
            ProcurementAdminRecipientOption(
                memberId=member.id,
                name=_member_display_name(member) or member.id,
                email=member.user.email if member.user else "",
            )
            for member in recipients
        ]
    )


async def list_procurement_requisitions(
    db: AsyncSession,
    ctx: MemberContext,
) -> AssetPurchaseRequisitionListResponse:
    query = (
        select(AssetPurchaseRequisition)
        .options(
            joinedload(AssetPurchaseRequisition.raisedBy).joinedload(Member.user),
            joinedload(AssetPurchaseRequisition.raisedBy).joinedload(Member.role),
            joinedload(AssetPurchaseRequisition.approvedBy).joinedload(Member.user),
            joinedload(AssetPurchaseRequisition.affectedEmployee).joinedload(Member.user),
            joinedload(AssetPurchaseRequisition.department),
            joinedload(AssetPurchaseRequisition.categoryDefinition),
            selectinload(AssetPurchaseRequisition.activityLogs)
            .joinedload(AssetPurchaseRequisitionActivityLog.actor)
            .joinedload(Member.user),
            selectinload(AssetPurchaseRequisition.purchaseOrders)
            .joinedload(AssetPurchaseOrder.recipient)
            .joinedload(Member.user),
            selectinload(AssetPurchaseRequisition.purchaseOrders)
            .joinedload(AssetPurchaseOrder.generatedBy)
            .joinedload(Member.user),
        )
        .where(AssetPurchaseRequisition.organizationId == ctx.organization.id)
        .order_by(AssetPurchaseRequisition.createdAt.desc())
    )
    if ctx.scope == "self":
        query = query.where(AssetPurchaseRequisition.raisedByMemberId == ctx.member.id)
    result = await db.execute(query)
    items = result.unique().scalars().all()
    return AssetPurchaseRequisitionListResponse(
        items=[_serialize_requisition(item, ctx.member) for item in items]
    )


async def get_procurement_requisition(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
) -> AssetPurchaseRequisitionRead:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if not _can_view_requisition(requisition, ctx.member.id, ctx.scope):
        raise HTTPException(status_code=403, detail="you dont have permission")
    return _serialize_requisition(requisition, ctx.member)


async def create_procurement_requisition(
    db: AsyncSession,
    ctx: MemberContext,
    payload: AssetPurchaseRequisitionCreateRequest,
) -> AssetPurchaseRequisitionRead:
    request_number = await _next_request_number(db, ctx.organization.id)
    requisition = AssetPurchaseRequisition(
        organizationId=ctx.organization.id,
        requestType=payload.requestType,
        status="DRAFT",
        requestNumber=request_number,
        raisedByMemberId=ctx.member.id,
        justification=payload.justification.strip(),
        requiredByDate=payload.requiredByDate,
        estimatedUnitCost=payload.estimatedUnitCost,
        estimatedQuantity=payload.estimatedQuantity,
        estimatedTotalCost=payload.estimatedTotalCost,
        vendorPreference=payload.vendorPreference.strip() if payload.vendorPreference else None,
        urgency=payload.urgency,
        costCenterOrDepartmentId=payload.costCenterOrDepartmentId,
        assetName=payload.assetName.strip() if payload.assetName else None,
        assetCode=payload.assetCode.strip() if payload.assetCode else None,
        categoryDefinitionId=payload.categoryDefinitionId,
        specificationNotes=payload.specificationNotes.strip() if payload.specificationNotes else None,
        replacementReason=payload.replacementReason.strip() if payload.replacementReason else None,
    )

    if payload.requestType == "REPLACEMENT":
        ticket, ticket_snapshot, asset_snapshot = await _get_replacement_ticket_context(
            db, ctx.organization.id, payload.maintenanceTicketId or ""
        )
        unit_result = await db.execute(
            select(AssetUnit).where(AssetUnit.id == ticket.assetUnitId)
        ) if ticket.assetUnitId else None
        unit = unit_result.scalar_one_or_none() if unit_result is not None else None
        requisition.maintenanceTicketId = ticket.id
        requisition.assetId = ticket.assetId
        requisition.assetUnitId = ticket.assetUnitId
        requisition.affectedEmployeeId = unit.currentHolderMemberId if unit else None
        requisition.originalPurchaseDate = ticket.asset.purchaseDate if ticket.asset else None
        requisition.warrantyExpiryDate = ticket.asset.warrantyExpiryDate if ticket.asset else None
        requisition.warrantyStatus = ticket_snapshot["warrantyStatus"]
        requisition.replacementMode = ticket.replacementDecision
        requisition.ticketSnapshot = ticket_snapshot
        requisition.assetSnapshot = asset_snapshot
        requisition.assetName = ticket.asset.name if ticket.asset else requisition.assetName
        requisition.assetCode = ticket.asset.assetCode if ticket.asset else requisition.assetCode
        requisition.categoryDefinitionId = ticket.asset.categoryDefinitionId if ticket.asset else requisition.categoryDefinitionId

    db.add(requisition)
    await db.flush()
    await _log_activity(db, ctx.organization.id, requisition.id, ctx.member.id, "CREATED")
    await db.commit()
    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=500, detail="Failed to save procurement requisition")
    return _serialize_requisition(saved, ctx.member)


async def issue_procurement_purchase_order(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
    payload: ProcurementPurchaseOrderCreateRequest,
) -> AssetPurchaseRequisitionRead:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if not _can_issue_purchase_order(requisition, ctx.member):
        raise HTTPException(status_code=403, detail="Only finance approvers can issue purchase orders")

    recipients = await _get_procurement_admin_recipients(db, ctx.organization.id)
    recipient = next(
        (
            member
            for member in recipients
            if member.id == payload.recipientMemberId
            and member.user is not None
            and member.user.email.lower() == payload.recipientEmail
        ),
        None,
    )
    if recipient is None or recipient.user is None:
        raise HTTPException(status_code=400, detail="Selected recipient is not a valid admin contact")

    org = await _get_org(db, ctx.organization.id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    sequence = await _next_purchase_order_number(db, ctx.organization.id)
    po_number = _purchase_order_number(sequence)
    recipient_name = _member_display_name(recipient) or recipient.user.email
    generated_by_name = _member_display_name(ctx.member) or "Finance"
    pdf_bytes = _render_purchase_order_pdf(
        requisition,
        po_number=po_number,
        organization_name=org.name,
        recipient_name=recipient_name,
        generated_by_name=generated_by_name,
    )

    file_name = f"{po_number.lower()}.pdf"
    storage_bucket = get_settings().procurement_po_bucket
    storage_path = f"{ctx.organization.id}/purchase-orders/{requisition.id}/{file_name}"
    try:
        await upload_private_file(
            bucket=storage_bucket,
            path=storage_path,
            content=pdf_bytes,
            content_type="application/pdf",
        )
    except SupabaseStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    purchase_order = AssetPurchaseOrder(
        organizationId=ctx.organization.id,
        requisitionId=requisition.id,
        poNumber=po_number,
        formatKey=payload.formatKey,
        status="GENERATED",
        storageBucket=storage_bucket,
        storagePath=storage_path,
        fileName=file_name,
        recipientMemberId=recipient.id,
        recipientEmail=recipient.user.email.lower(),
        generatedByMemberId=ctx.member.id,
        emailSubject=f"Purchase Order {po_number}",
    )
    db.add(purchase_order)
    await db.flush()

    email_error: str | None = None
    try:
        await send_procurement_purchase_order(
            to_email=recipient.user.email,
            recipient_name=recipient_name,
            org_slug=org.slug,
            po_number=po_number,
            requisition_label=f"APR-{requisition.requestNumber:05d}" if requisition.requestNumber else requisition.id,
            asset_name=requisition.assetName or requisition.requestType.title(),
            generated_by_name=generated_by_name,
            pdf_bytes=pdf_bytes,
            file_name=file_name,
        )
        purchase_order.status = "SENT"
        purchase_order.sentAt = datetime.now(UTC)
    except Exception as exc:
        email_error = "Failed to send purchase order email"
        purchase_order.status = "FAILED"
        purchase_order.emailError = str(exc)[:1000]

    db.add(purchase_order)
    await _log_activity(
        db,
        ctx.organization.id,
        requisition.id,
        ctx.member.id,
        "PO_SENT" if purchase_order.status == "SENT" else "PO_GENERATED",
        f"{po_number} -> {recipient.user.email}" + (f" | {payload.message}" if payload.message else ""),
    )
    await db.commit()

    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if email_error:
        raise HTTPException(status_code=502, detail=email_error)
    return _serialize_requisition(saved, ctx.member)


async def submit_procurement_requisition(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
) -> AssetPurchaseRequisitionRead:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if requisition.raisedByMemberId != ctx.member.id:
        raise HTTPException(status_code=403, detail="you dont have permission")
    if requisition.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Only draft requisitions can be submitted")
    if requisition.requestType == "REPLACEMENT" and not requisition.maintenanceTicketId:
        raise HTTPException(status_code=400, detail="Replacement purchasing requires a linked ticket")

    approvers = await _get_org_finance_approvers(db, ctx.organization.id)
    if not approvers:
        raise HTTPException(status_code=400, detail="No finance managers are configured for procurement approval")

    requisition.status = "PENDING_FINANCE_APPROVAL"
    db.add(requisition)
    await _log_activity(db, ctx.organization.id, requisition.id, ctx.member.id, "SUBMITTED")
    await db.commit()

    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    org = await _get_org(db, ctx.organization.id)
    if org is not None:
        await send_procurement_requisition_submitted(saved, org.slug, approvers, _member_display_name(ctx.member) or "Admin")
    return _serialize_requisition(saved, ctx.member)


async def approve_procurement_requisition(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
    payload: ProcurementDecisionRequest,
) -> AssetPurchaseRequisitionRead:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if not _can_finance_approve(requisition, ctx.member):
        raise HTTPException(status_code=403, detail="Only a finance manager can approve this requisition")

    requisition.status = "APPROVED"
    requisition.approvedByMemberId = ctx.member.id
    requisition.approvedAt = datetime.now(UTC)
    requisition.rejectedAt = None
    requisition.reviewerComment = (payload.comment or "").strip() or None
    db.add(requisition)
    await _log_activity(
        db,
        ctx.organization.id,
        requisition.id,
        ctx.member.id,
        "APPROVED",
        requisition.reviewerComment,
    )
    await db.commit()

    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    org = await _get_org(db, ctx.organization.id)
    if org is not None and saved.raisedBy is not None:
        await send_procurement_requisition_decided(
            saved,
            org.slug,
            saved.raisedBy,
            "APPROVED",
            requisition.reviewerComment,
        )
    return _serialize_requisition(saved, ctx.member)


async def reject_procurement_requisition(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
    payload: ProcurementDecisionRequest,
) -> AssetPurchaseRequisitionRead:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if not _can_finance_approve(requisition, ctx.member):
        raise HTTPException(status_code=403, detail="Only a finance manager can reject this requisition")
    comment = (payload.comment or "").strip()
    if not comment:
        raise HTTPException(status_code=400, detail="Comment is required to reject a requisition")

    requisition.status = "REJECTED"
    requisition.approvedByMemberId = None
    requisition.approvedAt = None
    requisition.rejectedAt = datetime.now(UTC)
    requisition.reviewerComment = comment
    db.add(requisition)
    await _log_activity(
        db,
        ctx.organization.id,
        requisition.id,
        ctx.member.id,
        "REJECTED",
        comment,
    )
    await db.commit()

    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    org = await _get_org(db, ctx.organization.id)
    if org is not None and saved.raisedBy is not None:
        await send_procurement_requisition_decided(
            saved,
            org.slug,
            saved.raisedBy,
            "REJECTED",
            comment,
        )
    return _serialize_requisition(saved, ctx.member)


async def cancel_procurement_requisition(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
) -> AssetPurchaseRequisitionRead:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if requisition.raisedByMemberId != ctx.member.id and ctx.scope == "self":
        raise HTTPException(status_code=403, detail="you dont have permission")
    if requisition.status not in {"DRAFT", "PENDING_FINANCE_APPROVAL"}:
        raise HTTPException(status_code=400, detail="This requisition cannot be cancelled")

    requisition.status = "CANCELLED"
    db.add(requisition)
    await _log_activity(db, ctx.organization.id, requisition.id, ctx.member.id, "CANCELLED")
    await db.commit()
    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    return _serialize_requisition(saved, ctx.member)
