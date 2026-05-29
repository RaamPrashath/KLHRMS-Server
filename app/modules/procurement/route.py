from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.procurement.controller import (
    handle_approve_requisition,
    handle_cancel_requisition,
    handle_create_requisition,
    handle_get_admin_recipients,
    handle_get_meta,
    handle_get_requisition,
    handle_issue_purchase_order,
    handle_list_requisitions,
    handle_reject_requisition,
    handle_submit_requisition,
)
from app.modules.procurement.schema import (
    AssetPurchaseRequisitionCreateRequest,
    AssetPurchaseRequisitionListResponse,
    AssetPurchaseRequisitionRead,
    ProcurementAdminRecipientsResponse,
    ProcurementDecisionRequest,
    ProcurementMetaResponse,
    ProcurementPurchaseOrderCreateRequest,
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


@router.get("", response_model=AssetPurchaseRequisitionListResponse)
async def list_procurement_requisitions_route(
    access: Annotated[
        MemberContext, Depends(require_permission("procurement", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetPurchaseRequisitionListResponse:
    return await handle_list_requisitions(access, db)


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


@router.post("/{requisition_id}/cancel", response_model=AssetPurchaseRequisitionRead)
async def cancel_procurement_requisition_route(
    requisition_id: str,
    access: Annotated[
        MemberContext, Depends(require_permission("procurement", "create", allow_self=True))
    ],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_cancel_requisition(access, db, requisition_id)


@router.post("/{requisition_id}/purchase-orders", response_model=AssetPurchaseRequisitionRead)
async def issue_procurement_purchase_order_route(
    requisition_id: str,
    body: ProcurementPurchaseOrderCreateRequest,
    access: Annotated[MemberContext, Depends(require_permission("procurement", "approve"))],
    db: DbSession,
) -> AssetPurchaseRequisitionRead:
    return await handle_issue_purchase_order(access, db, requisition_id, body)
