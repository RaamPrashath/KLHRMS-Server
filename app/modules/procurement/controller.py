from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.procurement.schema import (
    AssetPurchaseRequisitionCreateRequest,
    AssetPurchaseRequisitionListResponse,
    AssetPurchaseRequisitionRead,
    ProcurementAdminRecipientsResponse,
    ProcurementDecisionRequest,
    ProcurementMetaResponse,
    ProcurementPdfPreviewResponse,
    ProcurementPurchaseOrderDownloadResponse,
    ProcurementPurchaseOrderDraftResponse,
    ProcurementPurchaseOrderGenerateRequest,
    ProcurementPurchaseOrderIssueResponse,
    ProcurementPurchaseOrderListResponse,
    ProcurementPurchaseOrderTemplateRead,
    ProcurementPurchaseOrderTemplateUpdateRequest,
    ProcurementPurchaseOrderPreviewRequest,
)
from app.modules.procurement.service import (
    approve_procurement_requisition,
    cancel_procurement_requisition,
    create_procurement_requisition,
    get_procurement_admin_recipients,
    get_procurement_meta,
    get_procurement_purchase_order_download,
    get_procurement_purchase_order_draft,
    get_procurement_purchase_order_template,
    get_procurement_requisition,
    issue_procurement_purchase_order,
    list_procurement_purchase_orders,
    list_procurement_requisitions,
    preview_procurement_purchase_order,
    reject_procurement_requisition,
    submit_procurement_requisition,
    upsert_procurement_purchase_order_template,
)
from app.shared.deps.organization_member import MemberContext


async def handle_get_meta(ctx: MemberContext, db: AsyncSession) -> ProcurementMetaResponse:
    return await get_procurement_meta(db, ctx)


async def handle_get_admin_recipients(
    ctx: MemberContext, db: AsyncSession
) -> ProcurementAdminRecipientsResponse:
    return await get_procurement_admin_recipients(db, ctx)


async def handle_list_requisitions(
    ctx: MemberContext,
    db: AsyncSession,
) -> AssetPurchaseRequisitionListResponse:
    return await list_procurement_requisitions(db, ctx)


async def handle_list_purchase_orders(
    ctx: MemberContext,
    db: AsyncSession,
) -> ProcurementPurchaseOrderListResponse:
    return await list_procurement_purchase_orders(db, ctx)


async def handle_get_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> AssetPurchaseRequisitionRead:
    return await get_procurement_requisition(db, ctx, requisition_id)


async def handle_create_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    payload: AssetPurchaseRequisitionCreateRequest,
) -> AssetPurchaseRequisitionRead:
    return await create_procurement_requisition(db, ctx, payload)


async def handle_submit_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> AssetPurchaseRequisitionRead:
    return await submit_procurement_requisition(db, ctx, requisition_id)


async def handle_approve_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    payload: ProcurementDecisionRequest,
) -> AssetPurchaseRequisitionRead:
    return await approve_procurement_requisition(db, ctx, requisition_id, payload)


async def handle_reject_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    payload: ProcurementDecisionRequest,
) -> AssetPurchaseRequisitionRead:
    return await reject_procurement_requisition(db, ctx, requisition_id, payload)


async def handle_cancel_requisition(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> AssetPurchaseRequisitionRead:
    return await cancel_procurement_requisition(db, ctx, requisition_id)


async def handle_get_purchase_order_draft(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
) -> ProcurementPurchaseOrderDraftResponse:
    return await get_procurement_purchase_order_draft(db, ctx, requisition_id)


async def handle_get_purchase_order_template(
    ctx: MemberContext,
    db: AsyncSession,
) -> ProcurementPurchaseOrderTemplateRead:
    return await get_procurement_purchase_order_template(db, ctx)


async def handle_upsert_purchase_order_template(
    ctx: MemberContext,
    db: AsyncSession,
    payload: ProcurementPurchaseOrderTemplateUpdateRequest,
) -> ProcurementPurchaseOrderTemplateRead:
    return await upsert_procurement_purchase_order_template(db, ctx, payload)


async def handle_preview_purchase_order(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    payload: ProcurementPurchaseOrderPreviewRequest,
) -> ProcurementPdfPreviewResponse:
    return await preview_procurement_purchase_order(db, ctx, requisition_id, payload)


async def handle_issue_purchase_order(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    payload: ProcurementPurchaseOrderGenerateRequest,
) -> ProcurementPurchaseOrderIssueResponse:
    return await issue_procurement_purchase_order(db, ctx, requisition_id, payload)


async def handle_get_purchase_order_download(
    ctx: MemberContext,
    db: AsyncSession,
    purchase_order_id: str,
) -> ProcurementPurchaseOrderDownloadResponse:
    return await get_procurement_purchase_order_download(db, ctx, purchase_order_id)
