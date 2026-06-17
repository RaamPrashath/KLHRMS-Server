from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

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
    MemberAssignedAssetResponse,
    MemberTicketSummary,
    ReplacementRecord,
    ReplacementProvideRequest,
    ReplacementRaiseAppraisalRequest,
    SetReturnDateRequest,
)
from app.modules.assets.service import (
    archive_ticket,
    bulk_create_assets,
    create_asset_id,
    create_category,
    create_category_field,
    create_helpdesk_ticket,
    create_maintenance_record,
    delete_asset,
    delete_asset_id,
    delete_category,
    delete_category_field,
    export_asset_report,
    export_asset_report_pdf,
    export_asset_report_xlsx,
    get_asset,
    get_employee_asset_view,
    get_brand_model_analytics,
    get_asset_meta,
    get_dashboard,
    get_os_distribution_analytics,
    get_returned_assets,
    get_upcoming_warranty_feed,
    issue_assets,
    list_asset_ids,
    list_assets,
    list_available_groups,
    list_categories,
    list_member_assigned_assets,
    list_member_tickets,
    list_replacements,
    list_my_tickets,
    list_tickets,
    provide_replacement,
    raise_replacement_appraisal,
    request_asset_return,
    return_asset,
    set_replacement_return_date,
    unarchive_ticket,
    withdraw_helpdesk_ticket,
    update_asset_id,
    update_category,
    update_category_field,
    update_maintenance_record,
    update_maintenance_record_by_id,
    upsert_asset,
)
from app.modules.assets.export_service import (
    generate_register_export,
    generate_issued_export,
    generate_returned_export,
    generate_inventory_export,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_assets(
    ctx: MemberContext, db: AsyncSession, filters: AssetFilters
) -> AssetListResponse:
    return await list_assets(db, ctx, filters)


async def handle_get_asset(
    ctx: MemberContext, db: AsyncSession, asset_id: str
) -> AssetDetailResponse:
    return await get_asset(db, ctx, asset_id)


async def handle_get_employee_asset_view(
    ctx: MemberContext,
    db: AsyncSession,
) -> EmployeeAssetViewResponse:
    return await get_employee_asset_view(db, ctx)


async def handle_create_asset(
    ctx: MemberContext, db: AsyncSession, payload: AssetUpsertRequest
) -> AssetDetailResponse:
    return await upsert_asset(db, ctx, payload)


async def handle_update_asset(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id: str,
    payload: AssetUpsertRequest,
) -> AssetDetailResponse:
    return await upsert_asset(db, ctx, payload, asset_id=asset_id)


async def handle_delete_asset(ctx: MemberContext, db: AsyncSession, asset_id: str) -> None:
    await delete_asset(db, ctx, asset_id)


async def handle_return_asset(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id: str,
    payload: AssetReturnRequest,
) -> AssetDetailResponse:
    return await return_asset(db, ctx, asset_id, payload)


async def handle_request_asset_return(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id: str,
) -> AssetReturnRequestedResponse:
    result = await request_asset_return(db, ctx, asset_id)
    return AssetReturnRequestedResponse(**result)


async def handle_create_maintenance(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id: str,
    payload: AssetMaintenanceCreateRequest,
) -> AssetDetailResponse:
    return await create_maintenance_record(db, ctx, asset_id, payload)


async def handle_update_maintenance(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id: str,
    maintenance_id: str,
    payload: AssetMaintenanceUpdateRequest,
) -> AssetDetailResponse:
    return await update_maintenance_record(db, ctx, asset_id, maintenance_id, payload)


async def handle_create_helpdesk_ticket(
    ctx: MemberContext,
    db: AsyncSession,
    payload: HelpdeskTicketCreateRequest,
) -> MyTicketResponse:
    return await create_helpdesk_ticket(db, ctx, payload)


async def handle_withdraw_helpdesk_ticket(
    ctx: MemberContext,
    db: AsyncSession,
    ticket_id: str,
) -> MyTicketResponse:
    return await withdraw_helpdesk_ticket(db, ctx, ticket_id)


async def handle_update_maintenance_by_id(
    ctx: MemberContext,
    db: AsyncSession,
    maintenance_id: str,
    payload: AssetMaintenanceUpdateRequest,
) -> None:
    await update_maintenance_record_by_id(db, ctx, maintenance_id, payload)


async def handle_get_dashboard(ctx: MemberContext, db: AsyncSession) -> AssetDashboardResponse:
    return await get_dashboard(db, ctx)


async def handle_get_brand_model_analytics(
    ctx: MemberContext, db: AsyncSession
) -> AssetBrandModelAnalyticsResponse:
    return await get_brand_model_analytics(db, ctx)


async def handle_get_os_distribution_analytics(
    ctx: MemberContext, db: AsyncSession
) -> AssetOsDistributionResponse:
    return await get_os_distribution_analytics(db, ctx)


async def handle_get_upcoming_warranty_feed(
    ctx: MemberContext, db: AsyncSession
) -> WarrantyExpirationFeedResponse:
    return await get_upcoming_warranty_feed(db, ctx)


async def handle_get_returned_assets(
    ctx: MemberContext, db: AsyncSession
) -> list[ReturnedAssetSummary]:
    return await get_returned_assets(db, ctx)


async def handle_get_meta(ctx: MemberContext, db: AsyncSession) -> AssetMetaResponse:
    return await get_asset_meta(db, ctx)


async def handle_list_my_tickets(ctx: MemberContext, db: AsyncSession) -> list[MyTicketResponse]:
    return await list_my_tickets(db, ctx)


async def handle_list_tickets(
    ctx: MemberContext, db: AsyncSession, archived: bool = False
) -> list[MaintenanceTicketResponse]:
    return await list_tickets(db, ctx, archived=archived)


async def handle_archive_ticket(
    ctx: MemberContext, db: AsyncSession, ticket_id: str
) -> MaintenanceTicketResponse:
    return await archive_ticket(db, ctx, ticket_id)


async def handle_unarchive_ticket(
    ctx: MemberContext, db: AsyncSession, ticket_id: str
) -> MaintenanceTicketResponse:
    return await unarchive_ticket(db, ctx, ticket_id)


async def handle_export_report(
    ctx: MemberContext, db: AsyncSession, payload: AssetReportRequest
) -> str:
    return await export_asset_report(db, ctx, payload)


async def handle_export_report_pdf(
    ctx: MemberContext, db: AsyncSession, payload: AssetReportRequest
) -> bytes:
    return await export_asset_report_pdf(db, ctx, payload)


async def handle_export_report_xlsx(
    ctx: MemberContext, db: AsyncSession, payload: AssetReportRequest
) -> bytes:
    return await export_asset_report_xlsx(db, ctx, payload)


async def handle_export_register(
    ctx: MemberContext, db: AsyncSession, payload: AssetExportRequest
) -> bytes | str:
    return await generate_register_export(db, ctx, payload)


async def handle_export_issued(
    ctx: MemberContext, db: AsyncSession, payload: AssetExportRequest
) -> bytes | str:
    return await generate_issued_export(db, ctx, payload)


async def handle_export_returned(
    ctx: MemberContext, db: AsyncSession, payload: AssetExportRequest
) -> bytes | str:
    return await generate_returned_export(db, ctx, payload)


async def handle_export_inventory(
    ctx: MemberContext, db: AsyncSession, payload: AssetExportRequest
) -> bytes | str:
    return await generate_inventory_export(db, ctx, payload)


# ── Asset ID CRUD handlers ────────────────────────────────────────────────────


async def handle_create_asset_id(
    ctx: MemberContext,
    db: AsyncSession,
    payload: AssetIdCreate,
) -> AssetIdResponse:
    return await create_asset_id(db, ctx, payload)


async def handle_list_asset_ids(
    ctx: MemberContext,
    db: AsyncSession,
) -> list[AssetIdResponse]:
    return await list_asset_ids(db, ctx)


async def handle_update_asset_id(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id_id: str,
    payload: AssetIdUpdate,
) -> AssetIdResponse:
    return await update_asset_id(db, ctx, asset_id_id, payload)


async def handle_delete_asset_id(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id_id: str,
) -> None:
    await delete_asset_id(db, ctx, asset_id_id)


# ── Category CRUD handlers ─────────────────────────────────────────────────────


async def handle_create_category(
    ctx: MemberContext,
    db: AsyncSession,
    payload: AssetCategoryCreate,
) -> AssetCategoryResponse:
    return await create_category(db, ctx, payload)


async def handle_list_categories(
    ctx: MemberContext, db: AsyncSession
) -> list[AssetCategoryResponse]:
    return await list_categories(db, ctx)


async def handle_update_category(
    ctx: MemberContext,
    db: AsyncSession,
    category_id: str,
    payload: AssetCategoryUpdate,
) -> AssetCategoryResponse:
    return await update_category(db, ctx, category_id, payload)


async def handle_delete_category(ctx: MemberContext, db: AsyncSession, category_id: str) -> None:
    await delete_category(db, ctx, category_id)


async def handle_create_category_field(
    ctx: MemberContext,
    db: AsyncSession,
    category_id: str,
    payload: CategoryFieldDefinitionCreate,
) -> CategoryFieldDefinitionResponse:
    return await create_category_field(db, ctx, category_id, payload)


async def handle_update_category_field(
    ctx: MemberContext,
    db: AsyncSession,
    field_id: str,
    payload: CategoryFieldDefinitionUpdate,
) -> CategoryFieldDefinitionResponse:
    return await update_category_field(db, ctx, field_id, payload)


async def handle_delete_category_field(ctx: MemberContext, db: AsyncSession, field_id: str) -> None:
    await delete_category_field(db, ctx, field_id)


# ── New Bulk / Issue handlers ─────────────────────────────────────────────────


async def handle_bulk_create_assets(
    ctx: MemberContext,
    db: AsyncSession,
    payload: BulkAssetCreateRequest,
) -> list[AssetDetailResponse]:
    return await bulk_create_assets(db, ctx, payload)


async def handle_available_groups(
    ctx: MemberContext,
    db: AsyncSession,
) -> list[AvailableAssetGroupResponse]:
    return await list_available_groups(db, ctx)


async def handle_issue_assets(
    ctx: MemberContext,
    db: AsyncSession,
    payload: AssetIssueRequest,
) -> AssetIssueResponse:
    return await issue_assets(db, ctx, payload)


# ── Replacement handlers ────────────────────────────────────────────────────


async def handle_list_member_assigned_assets(
    ctx: MemberContext,
    db: AsyncSession,
    member_id: str,
) -> list[MemberAssignedAssetResponse]:
    return await list_member_assigned_assets(db, ctx, member_id)


async def handle_list_member_tickets(
    ctx: MemberContext,
    db: AsyncSession,
    member_id: str,
) -> list[MemberTicketSummary]:
    return await list_member_tickets(db, ctx, member_id)


async def handle_list_replacements(
    ctx: MemberContext,
    db: AsyncSession,
) -> list[ReplacementRecord]:
    return await list_replacements(db, ctx)


async def handle_provide_replacement(
    ctx: MemberContext,
    db: AsyncSession,
    payload: ReplacementProvideRequest,
) -> ReplacementRecord:
    return await provide_replacement(db, ctx, payload)


async def handle_raise_replacement_appraisal(
    ctx: MemberContext,
    db: AsyncSession,
    payload: ReplacementRaiseAppraisalRequest,
) -> dict:
    return await raise_replacement_appraisal(db, ctx, payload)


async def handle_set_replacement_return_date(
    ctx: MemberContext,
    db: AsyncSession,
    assignment_id: str,
    payload: SetReturnDateRequest,
) -> dict:
    return await set_replacement_return_date(db, ctx, assignment_id, payload)
