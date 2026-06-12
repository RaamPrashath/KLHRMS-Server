from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.procurement.controller import (
    handle_approve_requisition,
    handle_cancel_requisition,
    handle_create_requisition,
    handle_get_admin_recipients,
    handle_get_meta,
    handle_get_purchase_order_download,
    handle_get_purchase_order_draft,
    handle_get_purchase_order_template,
    handle_get_requisition,
    handle_issue_purchase_order,
    handle_list_purchase_orders,
    handle_list_requisitions,
    handle_preview_purchase_order,
    handle_reject_requisition,
    handle_send_po_email,
    handle_submit_requisition,
    handle_update_requisition,
    handle_upsert_purchase_order_template,
)
from app.modules.procurement.schema import (
    AssetPurchaseRequisitionCreateRequest,
    AssetPurchaseRequisitionListResponse,
    AssetPurchaseRequisitionRead,
    AssetPurchaseRequisitionUpdateRequest,
    PaginationParams,
    ProcurementAdminRecipientsResponse,
    ProcurementDecisionRequest,
    ProcurementMetaResponse,
    ProcurementPdfPreviewResponse,
    ProcurementPurchaseOrderDownloadResponse,
    ProcurementPurchaseOrderDraftResponse,
    ProcurementPurchaseOrderGenerateRequest,
    ProcurementPurchaseOrderIssueResponse,
    ProcurementPurchaseOrderListResponse,
    ProcurementPurchaseOrderSendEmailRequest,
    ProcurementPurchaseOrderTemplateRead,
    ProcurementPurchaseOrderTemplateUpdateRequest,
    ProcurementPurchaseOrderPreviewRequest,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/procurement", tags=["procurement"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/meta", response_model=ProcurementMetaResponse)
async def get_procurement_meta_route(
    access: Annotated[
        MemberContext, Depends(require_permission("procurement", "view", allow_self=True))
    ],
    db: DbSession,
) -> ProcurementMetaResponse:
    return await handle_get_meta(access, db)


@router.get("/admin-recipients", response_model=ProcurementAdminRecipientsResponse)
async def get_procurement_admin_recipients_route(
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> ProcurementAdminRecipientsResponse:
    return await handle_get_admin_recipients(access, db)


@router.get("/purchase-order-template", response_model=ProcurementPurchaseOrderTemplateRead)
async def get_procurement_purchase_order_template_route(
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> ProcurementPurchaseOrderTemplateRead:
    return await handle_get_purchase_order_template(access, db)


@router.get("/purchase-orders", response_model=ProcurementPurchaseOrderListResponse)
async def list_procurement_purchase_orders_route(
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ProcurementPurchaseOrderListResponse:
    pagination = PaginationParams(limit=limit, offset=offset)
    return await handle_list_purchase_orders(access, db, pagination)


@router.get("/purchase-orders/{purchase_order_id}/download", response_model=ProcurementPurchaseOrderDownloadResponse)
async def get_procurement_purchase_order_download_route(
    purchase_order_id: str,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> ProcurementPurchaseOrderDownloadResponse:
    return await handle_get_purchase_order_download(access, db, purchase_order_id)


@router.put("/purchase-order-template", response_model=ProcurementPurchaseOrderTemplateRead)
async def upsert_procurement_purchase_order_template_route(
    body: ProcurementPurchaseOrderTemplateUpdateRequest,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> ProcurementPurchaseOrderTemplateRead:
    return await handle_upsert_purchase_order_template(access, db, body)


@router.get("", response_model=AssetPurchaseRequisitionListResponse)
async def list_procurement_requisitions_route(
    access: Annotated[
        MemberContext, Depends(require_permission("procurement", "view", allow_self=True))
    ],
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AssetPurchaseRequisitionListResponse:
    pagination = PaginationParams(limit=limit, offset=offset)
    return await handle_list_requisitions(access, db, pagination)


@router.get("/{requisition_id}", response_model=AssetPurchaseRequisitionRead)
async def get_procurement_requisition_route(
    requisition_id: str,
    access: Annotated[
        MemberContext, Depends(require_permission("procurement", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_get_requisition(access, db, requisition_id)


@router.post("", response_model=AssetPurchaseRequisitionRead, status_code=status.HTTP_201_CREATED)
async def create_procurement_requisition_route(
    body: AssetPurchaseRequisitionCreateRequest,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "create"))],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_create_requisition(access, db, body)


@router.post("/{requisition_id}/submit", response_model=AssetPurchaseRequisitionRead)
async def submit_procurement_requisition_route(
    requisition_id: str,
    access: Annotated[
        MemberContext, Depends(require_permission("procurement", "create", allow_self=True))
    ],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_submit_requisition(access, db, requisition_id)


@router.post("/{requisition_id}/approve", response_model=AssetPurchaseRequisitionRead)
async def approve_procurement_requisition_route(
    requisition_id: str,
    body: ProcurementDecisionRequest,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_approve_requisition(access, db, requisition_id, body)


@router.post("/{requisition_id}/reject", response_model=AssetPurchaseRequisitionRead)
async def reject_procurement_requisition_route(
    requisition_id: str,
    body: ProcurementDecisionRequest,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_reject_requisition(access, db, requisition_id, body)


@router.patch("/{requisition_id}", response_model=AssetPurchaseRequisitionRead)
async def update_procurement_requisition_route(
    requisition_id: str,
    body: AssetPurchaseRequisitionUpdateRequest,
    access: Annotated[
        MemberContext, Depends(require_permission("procurement", "edit", allow_self=True))
    ],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_update_requisition(access, db, requisition_id, body)


@router.post("/{requisition_id}/cancel", response_model=AssetPurchaseRequisitionRead)
async def cancel_procurement_requisition_route(
    requisition_id: str,
    access: Annotated[
        MemberContext, Depends(require_permission("procurement", "create", allow_self=True))
    ],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_cancel_requisition(access, db, requisition_id)


@router.get("/{requisition_id}/purchase-order-draft", response_model=ProcurementPurchaseOrderDraftResponse)
async def get_procurement_purchase_order_draft_route(
    requisition_id: str,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> ProcurementPurchaseOrderDraftResponse:
    return await handle_get_purchase_order_draft(access, db, requisition_id)


@router.post("/{requisition_id}/purchase-order-preview", response_model=ProcurementPdfPreviewResponse)
async def preview_procurement_purchase_order_route(
    requisition_id: str,
    body: ProcurementPurchaseOrderPreviewRequest,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> ProcurementPdfPreviewResponse:
    return await handle_preview_purchase_order(access, db, requisition_id, body)


@router.post("/{requisition_id}/purchase-orders", response_model=ProcurementPurchaseOrderIssueResponse)
async def issue_procurement_purchase_order_route(
    requisition_id: str,
    body: ProcurementPurchaseOrderGenerateRequest,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> ProcurementPurchaseOrderIssueResponse:
    return await handle_issue_purchase_order(access, db, requisition_id, body)


@router.post("/purchase-orders/{purchase_order_id}/send-email")
async def send_procurement_purchase_order_email_route(
    purchase_order_id: str,
    body: ProcurementPurchaseOrderSendEmailRequest,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> dict[str, str]:
    return await handle_send_po_email(access, db, purchase_order_id, body)
