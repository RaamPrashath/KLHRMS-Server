from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.procurement.schema import (
    AssetPurchaseRequisitionCreateRequest,
    AssetPurchaseRequisitionListResponse,
    AssetPurchaseRequisitionRead,
    ProcurementAdminRecipientsResponse,
    ProcurementDecisionRequest,
    ProcurementMetaResponse,
    ProcurementPurchaseOrderCreateRequest,
)
from app.modules.procurement.service import (
    approve_procurement_requisition,
    cancel_procurement_requisition,
    create_procurement_requisition,
    get_procurement_admin_recipients,
    get_procurement_meta,
    get_procurement_requisition,
    issue_procurement_purchase_order,
    list_procurement_requisitions,
    reject_procurement_requisition,
    submit_procurement_requisition,
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


async def handle_issue_purchase_order(
    ctx: MemberContext,
    db: AsyncSession,
    requisition_id: str,
    payload: ProcurementPurchaseOrderCreateRequest,
) -> AssetPurchaseRequisitionRead:
    return await issue_procurement_purchase_order(db, ctx, requisition_id, payload)
