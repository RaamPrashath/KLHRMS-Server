from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assets.controller import (
    handle_available_groups,
    handle_bulk_create_assets,
    handle_create_asset,
    handle_create_asset_id,
    handle_create_category,
    handle_create_category_field,
    handle_create_helpdesk_ticket,
    handle_create_maintenance,
    handle_delete_asset,
    handle_delete_asset_id,
    handle_delete_category,
    handle_delete_category_field,
    handle_export_register,
    handle_export_issued,
    handle_export_returned,
    handle_export_inventory,
    handle_export_report,
    handle_export_report_pdf,
    handle_export_report_xlsx,
    handle_get_asset,
    handle_get_brand_model_analytics,
    handle_get_dashboard,
    handle_get_employee_asset_view,
    handle_get_meta,
    handle_get_os_distribution_analytics,
    handle_get_returned_assets,
    handle_get_upcoming_warranty_feed,
    handle_issue_assets,
    handle_list_asset_ids,
    handle_request_asset_return,
    handle_list_assets,
    handle_list_categories,
    handle_list_my_tickets,
    handle_list_tickets,
    handle_return_asset,
    handle_update_asset,
    handle_update_asset_id,
    handle_update_category,
    handle_update_category_field,
    handle_update_maintenance,
    handle_update_maintenance_by_id,
    handle_withdraw_helpdesk_ticket,
    handle_list_member_assigned_assets,
    handle_list_member_tickets,
    handle_list_replacements,
    handle_provide_replacement,
    handle_raise_replacement_appraisal,
    handle_set_replacement_return_date,
)
from app.modules.assets.schema import (
    AssetCategoryCreate,
    AssetCategoryResponse,
    AssetCategoryUpdate,
    AssetBrandModelAnalyticsResponse,
    AssetDashboardResponse,
    AssetDetailResponse,
    EmployeeAssetViewResponse,
    AssetExportRequest,
    AssetFilters,
    AssetIdCreate,
    AssetIdResponse,
    AssetIdUpdate,
    AssetIssueRequest,
    AssetIssueResponse,
    AssetListResponse,
    ReturnedAssetSummary,
    AssetMaintenanceCreateRequest,
    AssetMaintenanceUpdateRequest,
    AssetMetaResponse,
    AssetOsDistributionResponse,
    AssetReportRequest,
    AssetReturnRequest,
    AssetReturnRequestedResponse,
    AssetUpsertRequest,
    AvailableAssetGroupResponse,
    BulkAssetCreateRequest,
    CategoryFieldDefinitionCreate,
    CategoryFieldDefinitionResponse,
    CategoryFieldDefinitionUpdate,
    HelpdeskTicketCreateRequest,
    MaintenanceTicketResponse,
    MyTicketResponse,
    WarrantyExpirationFeedResponse,
    ReplacementRecord,
    MemberAssignedAssetResponse,
    MemberTicketSummary,
    ReplacementProvideRequest,
    ReplacementRaiseAppraisalRequest,
    SetReturnDateRequest,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/assets", tags=["assets"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _filters(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    category_definition_id: str | None = Query(default=None, alias="category_definition_id"),
    status_filter: str | None = Query(default=None, alias="status"),
    current_holder_member_id: str | None = Query(default=None, alias="current_holder_member_id"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=5000),
) -> AssetFilters:
    return AssetFilters(
        search=search,
        category=category,
        categoryDefinitionId=category_definition_id,
        status=status_filter,
        currentHolderMemberId=current_holder_member_id,
        page=page,
        page_size=page_size,
    )


# ── Asset ID Endpoints ────────────────────────────────────────────────────────


@router.get("/asset-ids", response_model=list[AssetIdResponse])
async def list_asset_ids_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[AssetIdResponse]:
    return await handle_list_asset_ids(access, db)


@router.post("/asset-ids", response_model=AssetIdResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_id_route(
    body: AssetIdCreate,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetIdResponse:
    return await handle_create_asset_id(access, db, body)


@router.patch("/asset-ids/{asset_id_id}", response_model=AssetIdResponse)
async def update_asset_id_route(
    asset_id_id: str,
    body: AssetIdUpdate,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetIdResponse:
    return await handle_update_asset_id(access, db, asset_id_id, body)


@router.delete("/asset-ids/{asset_id_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_id_route(
    asset_id_id: str,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> Response:
    await handle_delete_asset_id(access, db, asset_id_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Category Endpoints ─────────────────────────────────────────────────────────


@router.get("/categories", response_model=list[AssetCategoryResponse])
async def list_categories_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[AssetCategoryResponse]:
    return await handle_list_categories(access, db)


@router.post(
    "/categories", response_model=AssetCategoryResponse, status_code=status.HTTP_201_CREATED
)
async def create_category_route(
    body: AssetCategoryCreate,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetCategoryResponse:
    return await handle_create_category(access, db, body)


@router.patch("/categories/{category_id}", response_model=AssetCategoryResponse)
async def update_category_route(
    category_id: str,
    body: AssetCategoryUpdate,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetCategoryResponse:
    return await handle_update_category(access, db, category_id, body)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_route(
    category_id: str,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> Response:
    await handle_delete_category(access, db, category_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Category Field Endpoints ───────────────────────────────────────────────────


@router.post(
    "/categories/{category_id}/fields",
    response_model=CategoryFieldDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category_field_route(
    category_id: str,
    body: CategoryFieldDefinitionCreate,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> CategoryFieldDefinitionResponse:
    return await handle_create_category_field(access, db, category_id, body)


@router.patch("/categories/fields/{field_id}", response_model=CategoryFieldDefinitionResponse)
async def update_category_field_route(
    field_id: str,
    body: CategoryFieldDefinitionUpdate,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> CategoryFieldDefinitionResponse:
    return await handle_update_category_field(access, db, field_id, body)


@router.delete("/categories/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category_field_route(
    field_id: str,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> Response:
    await handle_delete_category_field(access, db, field_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Asset Endpoints ────────────────────────────────────────────────────────────


@router.get("", response_model=AssetListResponse)
async def list_assets_route(
    filters: Annotated[AssetFilters, Depends(_filters)],
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetListResponse:
    return await handle_list_assets(access, db, filters)


@router.get("/employee-view", response_model=EmployeeAssetViewResponse)
async def get_employee_asset_view_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> EmployeeAssetViewResponse:
    return await handle_get_employee_asset_view(access, db)


@router.get("/dashboard", response_model=AssetDashboardResponse)
async def get_asset_dashboard(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetDashboardResponse:
    return await handle_get_dashboard(access, db)


@router.get("/returned", response_model=list[ReturnedAssetSummary])
async def get_returned_assets_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[ReturnedAssetSummary]:
    return await handle_get_returned_assets(access, db)


@router.get("/analytics/brand-models", response_model=AssetBrandModelAnalyticsResponse)
async def get_brand_model_analytics_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetBrandModelAnalyticsResponse:
    return await handle_get_brand_model_analytics(access, db)


@router.get("/analytics/os-distribution", response_model=AssetOsDistributionResponse)
async def get_os_distribution_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetOsDistributionResponse:
    return await handle_get_os_distribution_analytics(access, db)


@router.get("/warranty/upcoming", response_model=WarrantyExpirationFeedResponse)
async def get_upcoming_warranty_feed_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> WarrantyExpirationFeedResponse:
    return await handle_get_upcoming_warranty_feed(access, db)


@router.get("/tickets", response_model=list[MaintenanceTicketResponse])
async def list_tickets_route(
    access: Annotated[
        MemberContext, Depends(require_permission("maintenance", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[MaintenanceTicketResponse]:
    return await handle_list_tickets(access, db)


@router.get("/tickets/mine", response_model=list[MyTicketResponse])
async def list_my_tickets_route(
    access: Annotated[
        MemberContext, Depends(require_permission("helpdesk", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[MyTicketResponse]:
    return await handle_list_my_tickets(access, db)


@router.post("/helpdesk", response_model=MyTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_helpdesk_ticket_route(
    body: HelpdeskTicketCreateRequest,
    access: Annotated[
        MemberContext, Depends(require_permission("helpdesk", "view", allow_self=True))
    ],
    db: DbSession,
) -> MyTicketResponse:
    return await handle_create_helpdesk_ticket(access, db, body)


@router.post("/tickets/mine/{ticket_id}/withdraw", response_model=MyTicketResponse)
async def withdraw_helpdesk_ticket_route(
    ticket_id: str,
    access: Annotated[
        MemberContext, Depends(require_permission("helpdesk", "view", allow_self=True))
    ],
    db: DbSession,
) -> MyTicketResponse:
    return await handle_withdraw_helpdesk_ticket(access, db, ticket_id)


@router.get("/meta", response_model=AssetMetaResponse)
async def get_asset_meta(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetMetaResponse:
    return await handle_get_meta(access, db)


@router.get("/report.csv")
async def export_asset_report_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
    report_type: str = Query(alias="report_type"),
    member_id: str | None = Query(default=None, alias="member_id"),
) -> Response:
    csv_text = await handle_export_report(
        access,
        db,
        AssetReportRequest(reportType=report_type, memberId=member_id),
    )
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{report_type.lower()}-report.csv"'},
    )


@router.get("/report.pdf")
async def export_asset_report_pdf_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
    report_type: str = Query(alias="report_type"),
    member_id: str | None = Query(default=None, alias="member_id"),
) -> Response:
    pdf_bytes = await handle_export_report_pdf(
        access,
        db,
        AssetReportRequest(reportType=report_type, memberId=member_id),
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report_type.lower()}-report.pdf"'},
    )


@router.get("/report.xlsx")
async def export_asset_report_xlsx_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
    report_type: str = Query(alias="report_type"),
    member_id: str | None = Query(default=None, alias="member_id"),
) -> Response:
    xlsx_bytes = await handle_export_report_xlsx(
        access,
        db,
        AssetReportRequest(reportType=report_type, memberId=member_id),
    )
    return Response(
        content=xlsx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{report_type.lower()}-report.xlsx"'
        },
    )


def _export_response(
    content: bytes | str,
    fmt: str,
    filename: str,
) -> Response:
    if fmt == "csv":
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )
    elif fmt == "pdf":
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
        )
    else:
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )


@router.post("/export/register")
async def export_register_route(
    body: AssetExportRequest,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> Response:
    result = await handle_export_register(access, db, body)
    return _export_response(result, body.format, "asset-register")


@router.post("/export/issued")
async def export_issued_route(
    body: AssetExportRequest,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> Response:
    result = await handle_export_issued(access, db, body)
    return _export_response(result, body.format, "issued-assets")


@router.post("/export/returned")
async def export_returned_route(
    body: AssetExportRequest,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> Response:
    result = await handle_export_returned(access, db, body)
    return _export_response(result, body.format, "returned-assets")


@router.post("/export/inventory")
async def export_inventory_route(
    body: AssetExportRequest,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "edit"))
    ],
    db: DbSession,
) -> Response:
    result = await handle_export_inventory(access, db, body)
    return _export_response(result, body.format, "inventory")


@router.post(
    "/bulk-create", response_model=list[AssetDetailResponse], status_code=status.HTTP_201_CREATED
)
async def bulk_create_assets(
    body: BulkAssetCreateRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "create"))],
    db: DbSession,
) -> list[AssetDetailResponse]:
    return await handle_bulk_create_assets(access, db, body)


@router.get("/available-groups", response_model=list[AvailableAssetGroupResponse])
async def available_groups_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[AvailableAssetGroupResponse]:
    return await handle_available_groups(access, db)


@router.post("/issue", response_model=AssetIssueResponse, status_code=status.HTTP_201_CREATED)
async def issue_assets_route(
    body: AssetIssueRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetIssueResponse:
    return await handle_issue_assets(access, db, body)


# ── Replacement Routes ──────────────────────────────────────────────────────


@router.get("/replacements", response_model=list[ReplacementRecord])
async def list_replacements_route(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[ReplacementRecord]:
    return await handle_list_replacements(access, db)


@router.post(
    "/replacement/provide",
    response_model=ReplacementRecord,
    status_code=status.HTTP_201_CREATED,
)
async def provide_replacement_route(
    body: ReplacementProvideRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> ReplacementRecord:
    return await handle_provide_replacement(access, db, body)


@router.post("/replacement/raise-appraisal")
async def raise_replacement_appraisal_route(
    body: ReplacementRaiseAppraisalRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> dict:
    return await handle_raise_replacement_appraisal(access, db, body)


@router.patch("/replacements/{assignment_id}/return-date")
async def set_replacement_return_date_route(
    assignment_id: str,
    body: SetReturnDateRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> dict:
    return await handle_set_replacement_return_date(access, db, assignment_id, body)


@router.get("/members/{member_id}/assigned-assets", response_model=list[MemberAssignedAssetResponse])
async def list_member_assigned_assets_route(
    member_id: str,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[MemberAssignedAssetResponse]:
    return await handle_list_member_assigned_assets(access, db, member_id)


@router.get("/members/{member_id}/tickets", response_model=list[MemberTicketSummary])
async def list_member_tickets_route(
    member_id: str,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> list[MemberTicketSummary]:
    return await handle_list_member_tickets(access, db, member_id)


@router.post("/{asset_id}/request-return", response_model=AssetReturnRequestedResponse)
async def request_asset_return_route(
    asset_id: str,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetReturnRequestedResponse:
    return await handle_request_asset_return(access, db, asset_id)


@router.get("/{asset_id}", response_model=AssetDetailResponse)
async def get_asset_detail(
    asset_id: str,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetDetailResponse:
    return await handle_get_asset(access, db, asset_id)


@router.post("", response_model=AssetDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    body: AssetUpsertRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "create"))],
    db: DbSession,
) -> AssetDetailResponse:
    return await handle_create_asset(access, db, body)


@router.patch("/{asset_id}", response_model=AssetDetailResponse)
async def update_asset(
    asset_id: str,
    body: AssetUpsertRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetDetailResponse:
    return await handle_update_asset(access, db, asset_id, body)


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_route(
    asset_id: str,
    access: Annotated[MemberContext, Depends(require_permission("assets", "delete"))],
    db: DbSession,
) -> Response:
    await handle_delete_asset(access, db, asset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{asset_id}/return", response_model=AssetDetailResponse)
async def return_asset_route(
    asset_id: str,
    body: AssetReturnRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetDetailResponse:
    return await handle_return_asset(access, db, asset_id, body)


@router.post("/{asset_id}/maintenance", response_model=AssetDetailResponse)
async def create_maintenance_route(
    asset_id: str,
    body: AssetMaintenanceCreateRequest,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> AssetDetailResponse:
    return await handle_create_maintenance(access, db, asset_id, body)


@router.patch("/{asset_id}/maintenance/{maintenance_id}", response_model=AssetDetailResponse)
async def update_maintenance_route(
    asset_id: str,
    maintenance_id: str,
    body: AssetMaintenanceUpdateRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetDetailResponse:
    return await handle_update_maintenance(access, db, asset_id, maintenance_id, body)


@router.patch("/maintenance/{maintenance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_maintenance_by_id_route(
    maintenance_id: str,
    body: AssetMaintenanceUpdateRequest,
    access: Annotated[MemberContext, Depends(require_permission("maintenance", "edit"))],
    db: DbSession,
) -> Response:
    await handle_update_maintenance_by_id(access, db, maintenance_id, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
