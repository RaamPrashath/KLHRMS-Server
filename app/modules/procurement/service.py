from __future__ import annotations

import base64
import functools
import html
import io
import os
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import Image as PlatypusImage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.integrations.storage.supabase_storage import (
    SupabaseStorageError,
    create_private_file_signed_url,
    upload_private_file,
)
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
from app.models.procurement_purchase_order_template import ProcurementPurchaseOrderTemplate
from app.models.role import Role
from app.modules.assets.service import _derive_asset_status, _members_with_asset_admin_scope
from app.modules.notifications.service import (
    NotificationCreateInput,
    create_notification_batch,
)
from app.modules.procurement.schema import (
    AssetPurchaseRequisitionCreateRequest,
    AssetPurchaseRequisitionListResponse,
    AssetPurchaseRequisitionRead,
    AssetPurchaseRequisitionUpdateRequest,
    PaginationMeta,
    PaginationParams,
    ProcurementActivityEntry,
    ProcurementAdminRecipientOption,
    ProcurementAdminRecipientsResponse,
    ProcurementCategoryOption,
    ProcurementDecisionRequest,
    ProcurementDepartmentOption,
    ProcurementMetaResponse,
    ProcurementOrganizationDraftRead,
    ProcurementPdfPreviewResponse,
    ProcurementPurchaseOrderDownloadResponse,
    ProcurementPurchaseOrderDraftPayload,
    ProcurementPurchaseOrderDraftResponse,
    ProcurementPurchaseOrderGenerateRequest,
    ProcurementPurchaseOrderIssueResponse,
    ProcurementPurchaseOrderLineItemPayload,
    ProcurementPurchaseOrderListItemRead,
    ProcurementPurchaseOrderListResponse,
    ProcurementPurchaseOrderPreviewRequest,
    ProcurementPurchaseOrderRead,
    ProcurementPurchaseOrderTemplatePayload,
    ProcurementPurchaseOrderTemplateRead,
    ProcurementPurchaseOrderTemplateUpdateRequest,
    ProcurementReplacementTicketOption,
    ProcurementSnapshotRead,
)
from app.shared.config import get_settings
from app.shared.deps.organization_member import MemberContext
from app.shared.notifications.email import (

    is_resend_email_configured,
    send_procurement_purchase_order,
    send_procurement_requisition_decided,
    send_procurement_requisition_submitted,
)
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


def _can_finance_approve(
    requisition: AssetPurchaseRequisition,
    actor: Member,
) -> bool:
    if requisition.status != "PENDING_FINANCE_APPROVAL":
        return False
    if actor.role is None:
        return False
    scope = get_permission_scope(actor.role.permissions, "procurement", "approve")
    return scope is not None and scope not in ("none", "self")


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
        if member.role is not None
        and get_permission_scope(member.role.permissions, "procurement", "approve") not in (None, "none", "self")
    ]


def _can_issue_purchase_order(requisition: AssetPurchaseRequisition, actor: Member) -> bool:
    if requisition.status != "APPROVED" or actor.role is None:
        return False
    scope = get_permission_scope(actor.role.permissions, "procurement", "approve")
    return scope is not None and scope not in ("none", "self")


def _should_receive_procurement_po(role: Role | None) -> bool:
    if role is None:
        return False

    permissions = role.permissions or {}
    procurement_permissions = permissions.get("procurement") or {}
    return procurement_permissions.get("view") == "organization"


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


async def _load_purchase_order(
    db: AsyncSession,
    organization_id: str,
    purchase_order_id: str,
) -> AssetPurchaseOrder | None:
    result = await db.execute(
        select(AssetPurchaseOrder)
        .options(
            joinedload(AssetPurchaseOrder.recipient).joinedload(Member.user),
            joinedload(AssetPurchaseOrder.generatedBy).joinedload(Member.user),
            joinedload(AssetPurchaseOrder.requisition),
        )
        .where(
            AssetPurchaseOrder.organizationId == organization_id,
            AssetPurchaseOrder.id == purchase_order_id,
        )
    )
    return result.unique().scalar_one_or_none()


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
            templateVersion=entry.templateVersion,
            templateData=entry.templateData or {},
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
        approvalsPendingFinance=requisition.status == "PENDING",
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


async def _cancel_linked_replacement_ticket_after_approval(
    db: AsyncSession,
    requisition: AssetPurchaseRequisition,
) -> str | None:
    if requisition.requestType != "REPLACEMENT" or not requisition.maintenanceTicketId:
        return None

    result = await db.execute(
        select(AssetMaintenanceLog)
        .options(joinedload(AssetMaintenanceLog.asset).joinedload(Asset.units))
        .where(
            AssetMaintenanceLog.organizationId == requisition.organizationId,
            AssetMaintenanceLog.id == requisition.maintenanceTicketId,
        )
    )
    ticket = result.unique().scalar_one_or_none()
    if ticket is None or ticket.status in {"CANCELLED", "COMPLETED"}:
        return None

    ticket.status = "CANCELLED"

    asset = ticket.asset
    if asset is None:
        return ticket.ticketId

    if ticket.assetUnitId:
        unit = next((item for item in (asset.units or []) if item.id == ticket.assetUnitId), None)
        if unit is not None:
            unit.status = "DAMAGED"
        asset.status = _derive_asset_status(asset.units or [])
    else:
        asset.status = "DAMAGED"

    return ticket.ticketId


async def _next_purchase_order_number(db: AsyncSession, organization_id: str) -> int:
    result = await db.execute(
        select(func.count(AssetPurchaseOrder.id)).where(AssetPurchaseOrder.organizationId == organization_id)
    )
    current = result.scalar() or 0
    return current + 1


def _purchase_order_number(sequence: int) -> str:
    return f"PO-{datetime.now(UTC).year}-{sequence:05d}"


def _requisition_label(requisition: AssetPurchaseRequisition) -> str:
    return f"APR-{requisition.requestNumber:05d}" if requisition.requestNumber else requisition.id


def _is_procurement_email_configured() -> bool:
    return is_resend_email_configured()


def _round_money(value: float) -> float:
    return round(value, 2)


def _default_purchase_order_template(org: Organization) -> ProcurementPurchaseOrderTemplatePayload:
    return ProcurementPurchaseOrderTemplatePayload(
        name="Default Purchase Order",
        pageSize="A4",
        locale="en-IN",
        language="en",
        headerTitle="Purchase Order",
        headerSubtitle="Finance-approved procurement document",
        headerRichText=(
            "<p>Prepared for approved procurement requisitions with tenant-branded details, "
            "vendor information, and operational delivery instructions.</p>"
        ),
        footerRichText="<p>This purchase order was generated within KL HRMS.</p>",
        company={
            "displayName": org.name,
            "name": org.name,
            "logoUrl": org.logo,
            "address": None,
            "contactEmail": None,
            "contactPhone": None,
            "taxId": None,
        },
        signatory={"name": None, "title": "Authorized Signatory", "signatureImageUrl": None},
        defaultPaymentTermsHtml="<p>Net 30 days from invoice date unless otherwise agreed in writing.</p>",
        defaultNotesHtml="<p>Please reference the purchase order number on all invoices and shipping documents.</p>",
        defaultTermsHtml=(
            "<ul>"
            "<li>Deliver only against the items and quantities listed on this purchase order.</li>"
            "<li>Notify the finance team promptly if pricing, lead time, or availability changes.</li>"
            "</ul>"
        ),
    )


def _coerce_template_payload(
    value: ProcurementPurchaseOrderTemplatePayload | dict[str, Any],
) -> ProcurementPurchaseOrderTemplatePayload:
    if isinstance(value, ProcurementPurchaseOrderTemplatePayload):
        return value
    return ProcurementPurchaseOrderTemplatePayload(**value)


def _legacy_notes_to_html(
    justification: str | None,
    specification_notes: str | None,
    additional_notes: str | None,
) -> tuple[str | None, str | None]:
    note_parts = [part.strip() for part in [justification, specification_notes, additional_notes] if part and part.strip()]
    if not note_parts:
        return None, None
    notes_html = "".join(f"<p>{html.escape(part)}</p>" for part in note_parts[:2])
    terms_html = f"<p>{html.escape(note_parts[2])}</p>" if len(note_parts) > 2 else None
    return notes_html or None, terms_html


def _legacy_payload_to_snapshot(value: dict[str, Any]) -> tuple[ProcurementPurchaseOrderTemplatePayload, ProcurementPurchaseOrderDraftPayload]:
    legacy = value
    company = legacy.get("company") or {}
    vendor = legacy.get("vendor") or {}
    document = legacy.get("document") or {}
    line_item = legacy.get("lineItem") or {}
    notes = legacy.get("notes") or {}
    signatory = legacy.get("signatory") or {}
    notes_html, terms_html = _legacy_notes_to_html(
        notes.get("justification"),
        notes.get("specificationNotes"),
        notes.get("additionalNotes"),
    )
    template = ProcurementPurchaseOrderTemplatePayload(
        name="Default Purchase Order",
        pageSize="A4",
        locale="en-IN",
        language="en",
        headerTitle="Purchase Order",
        headerSubtitle=None,
        headerRichText=None,
        footerRichText=None,
        company={
            "displayName": company.get("displayName") or company.get("name") or "Organization",
            "name": company.get("name") or company.get("displayName") or "Organization",
            "logoUrl": company.get("logoUrl"),
            "address": company.get("address"),
            "contactEmail": company.get("contactEmail"),
            "contactPhone": company.get("contactPhone"),
            "taxId": company.get("taxId"),
        },
        signatory={
            "name": signatory.get("name"),
            "title": signatory.get("title"),
            "signatureImageUrl": signatory.get("signatureImageUrl"),
        },
        defaultPaymentTermsHtml=(
            f"<p>{html.escape(document.get('paymentTerms'))}</p>" if document.get("paymentTerms") else None
        ),
        defaultNotesHtml=notes_html,
        defaultTermsHtml=terms_html,
    )
    draft = ProcurementPurchaseOrderDraftPayload(
        document={
            "vendor": {
                "name": vendor.get("name") or "Vendor name",
                "contactPerson": vendor.get("contactPerson"),
                "email": vendor.get("email"),
                "phone": vendor.get("phone"),
                "address": vendor.get("address"),
                "taxId": vendor.get("taxId"),
            },
            "purchaseOrderDate": document.get("purchaseOrderDate") or date.today(),
            "deliveryDate": document.get("deliveryDate"),
            "billingAddress": company.get("address"),
            "shippingAddress": document.get("deliveryAddress"),
            "shippingMethod": document.get("shippingMethod"),
            "currency": document.get("currency") or "INR",
            "subject": notes.get("subject") or "Purchase order",
            "paymentTermsHtml": (
                f"<p>{html.escape(document.get('paymentTerms'))}</p>" if document.get("paymentTerms") else None
            ),
            "notesHtml": notes_html,
            "termsHtml": terms_html,
            "footerNotesHtml": None,
        },
        lineItems=[
            {
                "description": line_item.get("description") or "Asset purchase",
                "sku": line_item.get("sku"),
                "quantity": line_item.get("quantity") or 1,
                "unitPrice": _round_money(float(line_item.get("unitPrice") or 0)),
                "taxPercent": _round_money(float(line_item.get("taxPercent") or 0)),
                "total": _round_money(float(line_item.get("total") or 0)),
            }
        ],
    )
    return template, draft


def _coerce_document_payload(
    value: ProcurementPurchaseOrderDraftPayload | dict[str, Any],
) -> ProcurementPurchaseOrderDraftPayload:
    if isinstance(value, ProcurementPurchaseOrderDraftPayload):
        return value
    return ProcurementPurchaseOrderDraftPayload(**value)


def _coerce_purchase_order_snapshot(
    value: dict[str, Any] | None,
) -> tuple[ProcurementPurchaseOrderTemplatePayload | None, ProcurementPurchaseOrderDraftPayload | None]:
    if not value:
        return None, None
    if "template" in value and "document" in value:
        return _coerce_template_payload(value["template"]), _coerce_document_payload(value["document"])
    if "company" in value and "vendor" in value and "document" in value:
        return _legacy_payload_to_snapshot(value)
    return None, None


def _build_default_purchase_order_document(
    requisition: AssetPurchaseRequisition,
    template: ProcurementPurchaseOrderTemplatePayload,
) -> ProcurementPurchaseOrderDraftPayload:
    quantity = requisition.estimatedQuantity or 1
    unit_price = _to_float(requisition.estimatedUnitCost) or 0
    estimated_total = _to_float(requisition.estimatedTotalCost)
    total = estimated_total if estimated_total is not None else (quantity * unit_price)
    note_parts = [requisition.justification]
    if requisition.specificationNotes:
        note_parts.append(requisition.specificationNotes)

    return ProcurementPurchaseOrderDraftPayload(
        document={
            "vendor": {
                "name": requisition.vendorPreference or "Vendor name",
                "contactPerson": None,
                "email": None,
                "phone": None,
                "address": None,
                "taxId": None,
            },
            "purchaseOrderDate": date.today(),
            "deliveryDate": requisition.requiredByDate,
            "billingAddress": template.company.address,
            "shippingAddress": template.company.address,
            "shippingMethod": None,
            "currency": "INR",
            "subject": f"Purchase order for {requisition.assetName or requisition.requestType.title()}",
            "paymentTermsHtml": template.defaultPaymentTermsHtml,
            "notesHtml": "".join(f"<p>{html.escape(part)}</p>" for part in note_parts if part and part.strip()) or template.defaultNotesHtml,
            "termsHtml": template.defaultTermsHtml,
            "footerNotesHtml": None,
        },
        lineItems=[
            {
                "description": requisition.assetName or "Asset purchase",
                "sku": requisition.assetCode,
                "quantity": quantity,
                "unitPrice": _round_money(unit_price),
                "taxPercent": 0,
                "total": _round_money(total),
            }
        ],
    )


async def _get_procurement_purchase_order_template_record(
    db: AsyncSession,
    organization_id: str,
) -> ProcurementPurchaseOrderTemplate | None:
    result = await db.execute(
        select(ProcurementPurchaseOrderTemplate).where(
            ProcurementPurchaseOrderTemplate.organizationId == organization_id,
            ProcurementPurchaseOrderTemplate.status == "ACTIVE",
        )
    )
    return result.scalar_one_or_none()


def _serialize_template_record(
    record: ProcurementPurchaseOrderTemplate | None,
    template: ProcurementPurchaseOrderTemplatePayload,
) -> ProcurementPurchaseOrderTemplateRead:
    return ProcurementPurchaseOrderTemplateRead(
        id=record.id if record is not None else None,
        name=template.name,
        status=record.status if record is not None else "ACTIVE",
        templateVersion=f"v{record.templateVersion}" if record is not None else "v1",
        updatedAt=record.updatedAt if record is not None else None,
        template=template,
    )


@functools.lru_cache(maxsize=1)
def _resolve_pdf_font_family() -> dict[str, str]:
    _FONT_CANDIDATES = [
        ("KLPODefault", [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ], [
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\Arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]),
    ]
    for name, regular_candidates, bold_candidates in _FONT_CANDIDATES:
        regular_path = next((p for p in regular_candidates if os.path.exists(p)), None)
        bold_path = next((p for p in bold_candidates if os.path.exists(p)), None)
        if regular_path is not None and bold_path is not None:
            regular_name = f"{name}Regular"
            bold_name = f"{name}Bold"
            if regular_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(regular_name, regular_path))
            if bold_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
            return {"regular": regular_name, "bold": bold_name}

    return {"regular": "Helvetica", "bold": "Helvetica-Bold"}


async def _load_remote_image_bytes(url: str | None) -> bytes | None:
    if not url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
        return response.content
    except Exception:
        return None


def _normalize_rich_text_html(value: str | None) -> str:
    if not value:
        return ""
    markup = value.replace("&nbsp;", " ")
    markup = re.sub(r"<\s*strong\b", "<b", markup, flags=re.I)
    markup = re.sub(r"</\s*strong\s*>", "</b>", markup, flags=re.I)
    markup = re.sub(r"<\s*em\b", "<i", markup, flags=re.I)
    markup = re.sub(r"</\s*em\s*>", "</i>", markup, flags=re.I)
    markup = re.sub(r"<br\s*/?>", "<br/>", markup, flags=re.I)
    return markup


def _inline_markup(value: str | None) -> str:
    if not value:
        return ""
    markup = _normalize_rich_text_html(value)
    markup = re.sub(r"</?(?!b\b|i\b|u\b|br\b)[^>]+>", "", markup, flags=re.I)
    return markup.strip()


def _plain_text(value: str | None) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", _normalize_rich_text_html(value or ""))
    return " ".join(html.unescape(cleaned).split())


def _html_to_flowables(
    value: str | None,
    *,
    body_style: ParagraphStyle,
    heading_style: ParagraphStyle,
    subheading_style: ParagraphStyle,
    list_style: ParagraphStyle,
) -> list[Any]:
    if not value or not value.strip():
        return []

    normalized = _normalize_rich_text_html(value)
    block_pattern = re.compile(r"<(h2|h3|p|ul|ol)(?:\s[^>]*)?>(.*?)</\1>", re.I | re.S)
    blocks = block_pattern.findall(normalized)
    if not blocks:
        return [Paragraph(_inline_markup(normalized) or html.escape(_plain_text(normalized)), body_style)]

    flowables: list[Any] = []
    for tag, content in blocks:
        lowered = tag.lower()
        if lowered == "h2":
            flowables.append(Paragraph(_inline_markup(content), heading_style))
            continue
        if lowered == "h3":
            flowables.append(Paragraph(_inline_markup(content), subheading_style))
            continue
        if lowered == "p":
            flowables.append(Paragraph(_inline_markup(content), body_style))
            continue

        items = [
            ListItem(Paragraph(_inline_markup(match), list_style), leftIndent=0)
            for match in re.findall(r"<li(?:\s[^>]*)?>(.*?)</li>", content, flags=re.I | re.S)
        ]
        if items:
            flowables.append(
                ListFlowable(
                    items,
                    bulletType="bullet" if lowered == "ul" else "1",
                    leftIndent=14,
                )
            )
    return flowables


def _calculate_purchase_order_totals(
    line_items: list[ProcurementPurchaseOrderLineItemPayload],
) -> tuple[float, float, float]:
    subtotal = _round_money(sum(item.quantity * item.unitPrice for item in line_items))
    tax_total = _round_money(sum((item.quantity * item.unitPrice) * (item.taxPercent / 100) for item in line_items))
    grand_total = _round_money(sum(item.total for item in line_items))
    return subtotal, tax_total, grand_total


def _purchase_order_snapshot_payload(
    template: ProcurementPurchaseOrderTemplatePayload,
    document: ProcurementPurchaseOrderDraftPayload,
) -> dict[str, Any]:
    return {
        "template": template.model_dump(mode="json"),
        "document": document.model_dump(mode="json"),
    }


async def _render_purchase_order_pdf(
    requisition: AssetPurchaseRequisition,
    *,
    po_number: str,
    template: ProcurementPurchaseOrderTemplatePayload,
    document: ProcurementPurchaseOrderDraftPayload,
    generated_by_name: str,
) -> bytes:
    fonts = _resolve_pdf_font_family()
    buffer = io.BytesIO()
    page_size = A4 if template.pageSize == "A4" else LETTER
    margin = 0.7 * inch
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0.85 * inch,
        bottomMargin=0.85 * inch,
        title=f"{po_number}.pdf",
    )
    width, _ = page_size
    logo_bytes = await _load_remote_image_bytes(template.company.logoUrl)
    signature_bytes = await _load_remote_image_bytes(template.signatory.signatureImageUrl)
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "ProcurementBody",
        parent=styles["BodyText"],
        fontName=fonts["regular"],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#1D1D1F"),
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "ProcurementHeading",
        parent=styles["Heading2"],
        fontName=fonts["bold"],
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#1D1D1F"),
        spaceBefore=6,
        spaceAfter=6,
    )
    subheading_style = ParagraphStyle(
        "ProcurementSubheading",
        parent=styles["Heading3"],
        fontName=fonts["bold"],
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1D1D1F"),
        spaceBefore=4,
        spaceAfter=4,
    )
    label_style = ParagraphStyle(
        "ProcurementLabel",
        parent=styles["BodyText"],
        fontName=fonts["bold"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#6E6E73"),
        spaceAfter=2,
    )
    meta_value_style = ParagraphStyle(
        "ProcurementMetaValue",
        parent=styles["BodyText"],
        fontName=fonts["regular"],
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor("#1D1D1F"),
    )
    right_body_style = ParagraphStyle("ProcurementBodyRight", parent=body_style, alignment=TA_RIGHT)
    right_label_style = ParagraphStyle("ProcurementLabelRight", parent=label_style, alignment=TA_RIGHT)
    title_style = ParagraphStyle(
        "ProcurementTitle",
        parent=styles["Title"],
        fontName=fonts["bold"],
        fontSize=21,
        leading=24,
        textColor=colors.HexColor("#1D1D1F"),
        alignment=TA_RIGHT,
    )

    currency = (document.document.currency or "INR").upper()
    subtotal, tax_total, grand_total = _calculate_purchase_order_totals(document.lineItems)

    header_left: list[Any] = []
    if template.visibility.showLogo and logo_bytes:
        header_left.append(
            PlatypusImage(io.BytesIO(logo_bytes), width=1.35 * inch, height=0.65 * inch, kind="proportional")
        )
        header_left.append(Spacer(1, 6))
    header_left.append(Paragraph(html.escape(template.company.displayName), subheading_style))
    for line in [
        template.company.address,
        template.company.contactEmail,
        template.company.contactPhone,
        template.company.taxId,
    ]:
        if line:
            header_left.append(Paragraph(html.escape(line), body_style))

    header_right = [
        Paragraph(html.escape(template.headerTitle), title_style),
        Paragraph(html.escape(template.headerSubtitle or po_number), right_body_style),
        Spacer(1, 4),
        Paragraph(f"<b>PO Number</b><br/>{html.escape(po_number)}", right_body_style),
        Paragraph(f"<b>PO Date</b><br/>{document.document.purchaseOrderDate.isoformat()}", right_body_style),
    ]
    if document.document.deliveryDate:
        header_right.append(
            Paragraph(f"<b>Delivery</b><br/>{document.document.deliveryDate.isoformat()}", right_body_style)
        )

    story: list[Any] = [
        Table(
            [[header_left, header_right]],
            colWidths=[doc.width * 0.55, doc.width * 0.45],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        ),
        Spacer(1, 10),
    ]
    story.extend(
        _html_to_flowables(
            template.headerRichText,
            body_style=body_style,
            heading_style=heading_style,
            subheading_style=subheading_style,
            list_style=body_style,
        )
    )
    if template.headerRichText:
        story.append(Spacer(1, 6))
    story.append(HRFlowable(color=colors.HexColor("#E5E5EA"), width="100%"))
    story.append(Spacer(1, 10))

    requisition_label = _requisition_label(requisition)
    vendor_lines = [document.document.vendor.name]
    if template.visibility.showVendorContact:
        vendor_lines.extend(
            [
                document.document.vendor.contactPerson,
                document.document.vendor.email,
                document.document.vendor.phone,
                document.document.vendor.taxId,
            ]
        )
    if template.visibility.showVendorAddress:
        vendor_lines.append(document.document.vendor.address)
    vendor_value = "<br/>".join(html.escape(line) for line in vendor_lines if line)
    meta_rows = [
        [Paragraph("Vendor", label_style), Paragraph("Prepared By", right_label_style)],
        [Paragraph(vendor_value or "Vendor name", meta_value_style), Paragraph(html.escape(generated_by_name), right_body_style)],
        [Paragraph("Requisition", label_style), Paragraph("Shipping Method", right_label_style)],
        [Paragraph(html.escape(requisition_label), meta_value_style), Paragraph(html.escape(document.document.shippingMethod or "Not specified"), right_body_style)],
    ]
    if template.visibility.showBillingAddress:
        meta_rows.extend(
            [
                [Paragraph("Billing Address", label_style), Paragraph("", right_label_style)],
                [Paragraph(html.escape(document.document.billingAddress or "Not specified"), meta_value_style), Paragraph("", right_body_style)],
            ]
        )
    if template.visibility.showShippingAddress:
        meta_rows.extend(
            [
                [Paragraph("Shipping Address", label_style), Paragraph("", right_label_style)],
                [Paragraph(html.escape(document.document.shippingAddress or "Not specified"), meta_value_style), Paragraph("", right_body_style)],
            ]
        )
    story.append(
        Table(
            meta_rows,
            colWidths=[doc.width * 0.5, doc.width * 0.5],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            ),
        )
    )
    story.append(Spacer(1, 12))

    item_rows: list[list[Any]] = [
        [
            Paragraph("<b>Description</b>", label_style),
            Paragraph("<b>SKU</b>", label_style),
            Paragraph("<b>Qty</b>", label_style),
            Paragraph("<b>Unit Price</b>", label_style),
            Paragraph("<b>Tax</b>", label_style),
            Paragraph("<b>Total</b>", label_style),
        ]
    ]
    for item in document.lineItems:
        item_rows.append(
            [
                Paragraph(html.escape(item.description), body_style),
                Paragraph(html.escape(item.sku or "-"), body_style),
                Paragraph(str(item.quantity), body_style),
                Paragraph(f"{currency} {item.unitPrice:,.2f}", body_style),
                Paragraph(f"{item.taxPercent:.2f}%", body_style),
                Paragraph(f"{currency} {item.total:,.2f}", body_style),
            ]
        )
    story.append(
        Table(
            item_rows,
            repeatRows=1,
            colWidths=[
                doc.width * 0.33,
                doc.width * 0.12,
                doc.width * 0.08,
                doc.width * 0.16,
                doc.width * 0.11,
                doc.width * 0.20,
            ],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F7")),
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#E5E5EA")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        )
    )
    story.append(Spacer(1, 10))

    summary_rows = [
        [Paragraph("Subtotal", right_label_style), Paragraph(f"{currency} {subtotal:,.2f}", right_body_style)],
        [Paragraph("Tax", right_label_style), Paragraph(f"{currency} {tax_total:,.2f}", right_body_style)],
        [Paragraph("Grand Total", right_label_style), Paragraph(f"<b>{currency} {grand_total:,.2f}</b>", right_body_style)],
    ]
    story.append(
        Table(
            [[ "", Table(summary_rows, colWidths=[doc.width * 0.18, doc.width * 0.18], style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ])) ]],
            colWidths=[doc.width * 0.64, doc.width * 0.36],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            ),
        )
    )
    story.append(Spacer(1, 12))

    if template.visibility.showSubject and document.document.subject:
        story.append(Paragraph("Subject", heading_style))
        story.append(Paragraph(html.escape(document.document.subject), body_style))
    if template.visibility.showNotes:
        note_flowables = _html_to_flowables(
            document.document.notesHtml,
            body_style=body_style,
            heading_style=heading_style,
            subheading_style=subheading_style,
            list_style=body_style,
        )
        if note_flowables:
            story.append(Paragraph("Notes", heading_style))
            story.extend(note_flowables)
    if template.visibility.showPaymentTerms and document.document.paymentTermsHtml:
        story.append(Paragraph("Payment Terms", heading_style))
        story.extend(
            _html_to_flowables(
                document.document.paymentTermsHtml,
                body_style=body_style,
                heading_style=heading_style,
                subheading_style=subheading_style,
                list_style=body_style,
            )
        )
    if template.visibility.showTerms:
        term_flowables = _html_to_flowables(
            document.document.termsHtml,
            body_style=body_style,
            heading_style=heading_style,
            subheading_style=subheading_style,
            list_style=body_style,
        )
        if term_flowables:
            story.append(Paragraph("Terms", heading_style))
            story.extend(term_flowables)

    story.append(Spacer(1, 16))
    story.append(HRFlowable(color=colors.HexColor("#E5E5EA"), width="100%"))
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            html.escape(
                f"Approved by Finance on {(requisition.approvedAt.date().isoformat() if requisition.approvedAt else date.today().isoformat())}"
            ),
            body_style,
        )
    )
    if template.visibility.showSignature:
        if signature_bytes:
            story.append(
                PlatypusImage(io.BytesIO(signature_bytes), width=1.6 * inch, height=0.75 * inch, kind="proportional")
            )
        story.append(Spacer(1, 6))
        story.append(Paragraph(html.escape(template.signatory.name or generated_by_name), subheading_style))
        story.append(
            Paragraph(
                html.escape(template.signatory.title or "Authorized Signatory"),
                body_style,
            )
        )

    footer_lines = [
        _plain_text(template.footerRichText),
        _plain_text(document.document.footerNotesHtml),
    ]

    def draw_footer(pdf, _doc) -> None:
        if not template.visibility.showFooter:
            return
        pdf.saveState()
        pdf.setStrokeColor(colors.HexColor("#E5E5EA"))
        pdf.line(_doc.leftMargin, 0.62 * inch, width - _doc.rightMargin, 0.62 * inch)
        pdf.setFont(fonts["regular"], 8)
        pdf.setFillColor(colors.HexColor("#6E6E73"))
        text_y = 0.45 * inch
        for footer_line in [line for line in footer_lines if line]:
            pdf.drawString(_doc.leftMargin, text_y, footer_line[:120])
            text_y -= 10
        pdf.drawRightString(width - _doc.rightMargin, 0.45 * inch, f"Page {_doc.page}")
        pdf.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
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
    scope = get_permission_scope(ctx.member.role.permissions, "procurement", "approve")
    if ctx.member.role is None or scope in (None, "none", "self"):
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


async def list_procurement_purchase_orders(
    db: AsyncSession,
    ctx: MemberContext,
    pagination: PaginationParams | None = None,
) -> ProcurementPurchaseOrderListResponse:
    pagination = pagination or PaginationParams()

    scope = get_permission_scope(ctx.member.role.permissions, "procurement", "approve")
    if ctx.member.role is None or scope in (None, "none", "self"):
        raise HTTPException(status_code=403, detail="Only procurement approvers can access generated purchase orders")

    count_result = await db.execute(
        select(func.count(AssetPurchaseOrder.id)).where(AssetPurchaseOrder.organizationId == ctx.organization.id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(AssetPurchaseOrder)
        .options(
            joinedload(AssetPurchaseOrder.recipient).joinedload(Member.user),
            joinedload(AssetPurchaseOrder.generatedBy).joinedload(Member.user),
            joinedload(AssetPurchaseOrder.requisition),
        )
        .where(AssetPurchaseOrder.organizationId == ctx.organization.id)
        .order_by(AssetPurchaseOrder.generatedAt.desc(), AssetPurchaseOrder.createdAt.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    purchase_orders = result.unique().scalars().all()
    return ProcurementPurchaseOrderListResponse(
        items=[
            ProcurementPurchaseOrderListItemRead(
                id=entry.id,
                poNumber=entry.poNumber,
                status=entry.status,
                fileName=entry.fileName,
                generatedAt=entry.generatedAt,
                generatedByName=_member_display_name(entry.generatedBy),
                recipientName=_member_display_name(entry.recipient),
                recipientEmail=entry.recipientEmail,
                requestLabel=_requisition_label(entry.requisition) if entry.requisition is not None else None,
                assetName=entry.requisition.assetName if entry.requisition is not None else None,
                storageBucket=entry.storageBucket,
                storagePath=entry.storagePath,
            )
            for entry in purchase_orders
        ],
        pagination=PaginationMeta(total=total, limit=pagination.limit, offset=pagination.offset),
    )


async def get_procurement_purchase_order_download(
    db: AsyncSession,
    ctx: MemberContext,
    purchase_order_id: str,
) -> ProcurementPurchaseOrderDownloadResponse:
    scope = get_permission_scope(ctx.member.role.permissions, "procurement", "approve")
    if ctx.member.role is None or scope in (None, "none", "self"):
        raise HTTPException(status_code=403, detail="Only procurement approvers can download generated purchase orders")

    purchase_order = await _load_purchase_order(db, ctx.organization.id, purchase_order_id)
    if purchase_order is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")

    expires_in_seconds = 300
    try:
        download_url = await create_private_file_signed_url(
            bucket=purchase_order.storageBucket,
            path=purchase_order.storagePath,
            expires_in=expires_in_seconds,
        )
    except SupabaseStorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ProcurementPurchaseOrderDownloadResponse(
        fileName=purchase_order.fileName,
        downloadUrl=download_url,
        expiresInSeconds=expires_in_seconds,
    )


async def list_procurement_requisitions(
    db: AsyncSession,
    ctx: MemberContext,
    pagination: PaginationParams | None = None,
) -> AssetPurchaseRequisitionListResponse:
    pagination = pagination or PaginationParams()

    count_query = select(func.count(AssetPurchaseRequisition.id)).where(
        AssetPurchaseRequisition.organizationId == ctx.organization.id
    )
    if ctx.scope == "self":
        count_query = count_query.where(AssetPurchaseRequisition.raisedByMemberId == ctx.member.id)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

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
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    if ctx.scope == "self":
        query = query.where(AssetPurchaseRequisition.raisedByMemberId == ctx.member.id)
    result = await db.execute(query)
    items = result.unique().scalars().all()
    return AssetPurchaseRequisitionListResponse(
        items=[_serialize_requisition(item, ctx.member) for item in items],
        pagination=PaginationMeta(total=total, limit=pagination.limit, offset=pagination.offset),
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


async def get_procurement_purchase_order_template(
    db: AsyncSession,
    ctx: MemberContext,
) -> ProcurementPurchaseOrderTemplateRead:
    org = await _get_org(db, ctx.organization.id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    record = await _get_procurement_purchase_order_template_record(db, ctx.organization.id)
    template = _coerce_template_payload(record.templateData) if record is not None else _default_purchase_order_template(org)
    return _serialize_template_record(record, template)


async def upsert_procurement_purchase_order_template(
    db: AsyncSession,
    ctx: MemberContext,
    payload: ProcurementPurchaseOrderTemplateUpdateRequest,
) -> ProcurementPurchaseOrderTemplateRead:
    record = await _get_procurement_purchase_order_template_record(db, ctx.organization.id)
    if record is None:
        record = ProcurementPurchaseOrderTemplate(
            organizationId=ctx.organization.id,
            name=payload.template.name.strip(),
            status="ACTIVE",
            templateVersion=1,
            templateData=payload.template.model_dump(mode="json"),
            lastEditedByMemberId=ctx.member.id,
        )
    else:
        record.name = payload.template.name.strip()
        record.templateVersion += 1
        record.templateData = payload.template.model_dump(mode="json")
        record.lastEditedByMemberId = ctx.member.id
        record.status = "ACTIVE"

    db.add(record)
    await db.commit()
    await db.refresh(record)
    template = _coerce_template_payload(record.templateData)
    return _serialize_template_record(record, template)


async def get_procurement_purchase_order_draft(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
) -> ProcurementPurchaseOrderDraftResponse:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if not _can_issue_purchase_order(requisition, ctx.member):
        raise HTTPException(status_code=403, detail="Only finance approvers can access purchase order composer")

    org = await _get_org(db, ctx.organization.id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    template_record = await _get_procurement_purchase_order_template_record(db, ctx.organization.id)
    template = _coerce_template_payload(template_record.templateData) if template_record is not None else _default_purchase_order_template(org)
    latest_po = (requisition.purchaseOrders or [None])[0]
    saved_template, saved_document = _coerce_purchase_order_snapshot(latest_po.templateData if latest_po is not None else None)
    if saved_template is not None:
        template = saved_template
    document = saved_document or _build_default_purchase_order_document(requisition, template)

    recipients = await _get_procurement_admin_recipients(db, ctx.organization.id)
    return ProcurementPurchaseOrderDraftResponse(
        requisition=_serialize_requisition(requisition, ctx.member),
        organization=ProcurementOrganizationDraftRead(name=org.name, logoUrl=org.logo),
        adminRecipients=[
            ProcurementAdminRecipientOption(
                memberId=member.id,
                name=_member_display_name(member) or member.user.email,
                email=member.user.email.lower(),
            )
            for member in recipients
            if member.user is not None and member.user.email
        ],
        emailConfigured=_is_procurement_email_configured(),
        templateVersion=f"v{template_record.templateVersion}" if template_record is not None else "v1",
        templateRecordId=template_record.id if template_record is not None else None,
        template=template,
        document=document,
    )


async def preview_procurement_purchase_order(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
    payload: ProcurementPurchaseOrderPreviewRequest,
) -> ProcurementPdfPreviewResponse:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if not _can_issue_purchase_order(requisition, ctx.member):
        raise HTTPException(status_code=403, detail="Only finance approvers can preview purchase orders")

    pdf_bytes = await _render_purchase_order_pdf(
        requisition,
        po_number="PREVIEW",
        template=payload.template,
        document=payload.document,
        generated_by_name=_member_display_name(ctx.member) or "Finance",
    )
    return ProcurementPdfPreviewResponse(
        fileName=f"{_requisition_label(requisition).lower()}-preview.pdf",
        base64=base64.b64encode(pdf_bytes).decode("utf-8"),
    )


async def issue_procurement_purchase_order(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
    payload: ProcurementPurchaseOrderGenerateRequest,
) -> ProcurementPurchaseOrderIssueResponse:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if not _can_issue_purchase_order(requisition, ctx.member):
        raise HTTPException(status_code=403, detail="Only finance approvers can issue purchase orders")

    if requisition.purchaseOrders:
        raise HTTPException(status_code=400, detail="A purchase order has already been issued for this requisition")

    org = await _get_org(db, ctx.organization.id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    recipient: Member | None = None
    if payload.recipientMemberId and payload.recipientEmail:
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

    if payload.sendToAdmin:
        if not _is_procurement_email_configured():
            raise HTTPException(
                status_code=400,
                detail="Purchase order email is not configured on the server",
            )
        if recipient is None or recipient.user is None:
            raise HTTPException(status_code=400, detail="Selected recipient is not a valid admin contact")

    sequence = await _next_purchase_order_number(db, ctx.organization.id)
    po_number = _purchase_order_number(sequence)
    generated_by_name = _member_display_name(ctx.member) or "Finance"
    template_record = await _get_procurement_purchase_order_template_record(db, ctx.organization.id)
    pdf_bytes = await _render_purchase_order_pdf(
        requisition,
        po_number=po_number,
        template=payload.template,
        document=payload.document,
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
        recipientMemberId=recipient.id if recipient is not None else None,
        recipientEmail=(recipient.user.email.lower() if recipient is not None and recipient.user is not None else ""),
        generatedByMemberId=ctx.member.id,
        templateVersion=f"v{template_record.templateVersion}" if template_record is not None else "v1",
        templateData=_purchase_order_snapshot_payload(payload.template, payload.document),
        emailSubject=f"Purchase Order {po_number}",
    )
    db.add(purchase_order)
    await db.flush()

    email_error: str | None = None
    if payload.sendToAdmin and recipient is not None and recipient.user is not None:
        recipient_name = _member_display_name(recipient) or recipient.user.email
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
        (
            f"{po_number}"
            + (f" -> {recipient.user.email}" if recipient is not None and recipient.user is not None else "")
            + (f" | {payload.message}" if payload.message else "")
        ),
    )
    await db.commit()

    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    recipient_members: list[Member] = []
    if saved.raisedBy is not None:
        recipient_members.append(saved.raisedBy)
    if recipient is not None:
        recipient_members.append(recipient)
    recipient_members.append(ctx.member)

    seen_recipient_ids: set[str] = set()
    notifications: list[NotificationCreateInput] = []
    for member in recipient_members:
        if member.id in seen_recipient_ids:
            continue
        seen_recipient_ids.add(member.id)
        notifications.append(
            NotificationCreateInput(
                organization_id=ctx.organization.id,
                member_id=member.id,
                type="PROCUREMENT_PURCHASE_ORDER_SENT" if purchase_order.status == "SENT" else "PROCUREMENT_PURCHASE_ORDER_GENERATED",
                category="procurement",
                title=(
                    f"Purchase order {po_number} was sent"
                    if purchase_order.status == "SENT"
                    else f"Purchase order {po_number} was generated"
                ),
                message=(
                    f"{generated_by_name} {('sent' if purchase_order.status == 'SENT' else 'generated')} "
                    f"the purchase order for {requisition.assetName or requisition.requestType.title()}."
                ),
                action_url=f"/{org.slug}/procurement/purchase-orders/{requisition.id}",
                entity_type="PROCUREMENT_PURCHASE_ORDER",
                entity_id=purchase_order.id,
                metadata={
                    "poNumber": po_number,
                    "requisitionId": requisition.id,
                    "requisitionLabel": _requisition_label(requisition),
                    "status": purchase_order.status,
                },
            )
        )
    await create_notification_batch(db, notifications)
    await db.commit()
    if email_error:
        raise HTTPException(status_code=502, detail=email_error)
    return ProcurementPurchaseOrderIssueResponse(
        requisition=_serialize_requisition(saved, ctx.member),
        purchaseOrderId=purchase_order.id,
        poNumber=po_number,
        status=purchase_order.status,
        pdf=ProcurementPdfPreviewResponse(
            fileName=file_name,
            base64=base64.b64encode(pdf_bytes).decode("utf-8"),
        ),
    )


async def update_procurement_requisition(
    db: AsyncSession,
    ctx: MemberContext,
    requisition_id: str,
    payload: AssetPurchaseRequisitionUpdateRequest,
) -> AssetPurchaseRequisitionRead:
    requisition = await _load_requisition(db, ctx.organization.id, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    if requisition.raisedByMemberId != ctx.member.id and ctx.scope == "self":
        raise HTTPException(status_code=403, detail="You can only update your own requisitions")
    if requisition.status not in {"DRAFT", "PENDING"}:
        raise HTTPException(status_code=400, detail="Only draft or pending requisitions can be edited")

    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "urgency" in update_data:
        update_data["urgency"] = payload.urgency.upper()

    for field, value in update_data.items():
        setattr(requisition, field, value)

    db.add(requisition)
    await _log_activity(db, ctx.organization.id, requisition.id, ctx.member.id, "UPDATED")
    await db.commit()
    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=500, detail="Failed to reload updated requisition")
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

    requisition.status = "PENDING"
    db.add(requisition)
    await _log_activity(db, ctx.organization.id, requisition.id, ctx.member.id, "SUBMITTED")
    await db.commit()

    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    org = await _get_org(db, ctx.organization.id)
    if org is not None:
        await create_notification_batch(
            db,
            [
                NotificationCreateInput(
                    organization_id=ctx.organization.id,
                    member_id=approver.id,
                    type="PROCUREMENT_APPROVAL_REQUEST",
                    category="procurement",
                    title="Purchase requisition awaiting your approval",
                    message=(
                        f"{_member_display_name(ctx.member) or 'A requester'} submitted "
                        f"{_requisition_label(saved)} for finance approval."
                    ),
                    action_url=f"/{org.slug}/procurement?requisition={saved.id}",
                    entity_type="PROCUREMENT_REQUISITION",
                    entity_id=saved.id,
                    metadata={
                        "requisitionId": saved.id,
                        "requestNumber": saved.requestNumber,
                        "requestType": saved.requestType,
                    },
                )
                for approver in approvers
            ],
        )
        await db.commit()
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
    cancelled_ticket_id = await _cancel_linked_replacement_ticket_after_approval(db, requisition)
    db.add(requisition)
    await _log_activity(
        db,
        ctx.organization.id,
        requisition.id,
        ctx.member.id,
        "APPROVED",
        requisition.reviewerComment,
    )
    if cancelled_ticket_id is not None:
        await _log_activity(
            db,
            ctx.organization.id,
            requisition.id,
            ctx.member.id,
            "LINKED_TICKET_CANCELLED",
            f"{cancelled_ticket_id} auto-cancelled after finance approval",
        )
    await db.commit()

    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    org = await _get_org(db, ctx.organization.id)
    if org is not None and saved.raisedBy is not None:
        await create_notification_batch(
            db,
            [
                NotificationCreateInput(
                    organization_id=ctx.organization.id,
                    member_id=saved.raisedBy.id,
                    type="PROCUREMENT_APPROVED",
                    category="procurement",
                    title="Your purchase requisition was approved",
                    message=(
                        f"{_requisition_label(saved)} for {saved.assetName or saved.requestType.title()} "
                        f"was approved by {_member_display_name(ctx.member) or 'Finance'}."
                    ),
                    action_url=f"/{org.slug}/procurement?requisition={saved.id}",
                    entity_type="PROCUREMENT_REQUISITION",
                    entity_id=saved.id,
                    metadata={"decision": "APPROVED", "requisitionId": saved.id},
                )
            ],
        )
        await db.commit()
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
        await create_notification_batch(
            db,
            [
                NotificationCreateInput(
                    organization_id=ctx.organization.id,
                    member_id=saved.raisedBy.id,
                    type="PROCUREMENT_REJECTED",
                    category="procurement",
                    title="Your purchase requisition was rejected",
                    message=(
                        f"{_requisition_label(saved)} for {saved.assetName or saved.requestType.title()} "
                        f"was rejected by {_member_display_name(ctx.member) or 'Finance'}."
                    ),
                    action_url=f"/{org.slug}/procurement?requisition={saved.id}",
                    entity_type="PROCUREMENT_REQUISITION",
                    entity_id=saved.id,
                    metadata={"decision": "REJECTED", "requisitionId": saved.id},
                )
            ],
        )
        await db.commit()
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
    if requisition.status not in {"DRAFT", "PENDING"}:
        raise HTTPException(status_code=400, detail="This requisition cannot be cancelled")

    requisition.status = "CANCELLED"
    db.add(requisition)
    await _log_activity(db, ctx.organization.id, requisition.id, ctx.member.id, "CANCELLED")
    await db.commit()
    saved = await _load_requisition(db, ctx.organization.id, requisition.id)
    if saved is None:
        raise HTTPException(status_code=404, detail="Procurement requisition not found")
    return _serialize_requisition(saved, ctx.member)
