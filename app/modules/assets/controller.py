from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assets.schema import (
    AssetIdCreate,
    AssetIdUpdate,
    AssetIdResponse,
    AssetCategoryCreate,
    AssetCategoryResponse,
    AssetCategoryUpdate,
    AssetDashboardResponse,
    AssetDetailResponse,
    AssetFilters,
    AssetListResponse,
    AssetMaintenanceCreateRequest,
    AssetMaintenanceUpdateRequest,
    AssetMetaResponse,
    AssetProvideRequest,
    AssetReportRequest,
    AssetReturnRequest,
    AssetUpsertRequest,
    CategoryFieldDefinitionCreate,
    CategoryFieldDefinitionResponse,
    CategoryFieldDefinitionUpdate,
)
from app.modules.assets.service import (
    create_asset_id,
    list_asset_ids,
    update_asset_id,
    delete_asset_id,
    create_category,
    create_category_field,
    create_maintenance_record,
    delete_asset,
    delete_category,
    delete_category_field,
    export_asset_report,
    export_asset_report_pdf,
    get_asset,
    get_dashboard,
    get_asset_meta,
    list_categories,
    list_assets,
    provide_asset,
    return_asset,
    update_category,
    update_category_field,
    update_maintenance_record,
    upsert_asset,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_assets(ctx: MemberContext, db: AsyncSession, filters: AssetFilters) -> AssetListResponse:
    return await list_assets(db, ctx, filters)


async def handle_get_asset(ctx: MemberContext, db: AsyncSession, asset_id: str) -> AssetDetailResponse:
    return await get_asset(db, ctx, asset_id)


async def handle_create_asset(ctx: MemberContext, db: AsyncSession, payload: AssetUpsertRequest) -> AssetDetailResponse:
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


async def handle_provide_asset(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id: str,
    payload: AssetProvideRequest,
) -> AssetDetailResponse:
    return await provide_asset(db, ctx, asset_id, payload)


async def handle_return_asset(
    ctx: MemberContext,
    db: AsyncSession,
    asset_id: str,
    payload: AssetReturnRequest,
) -> AssetDetailResponse:
    return await return_asset(db, ctx, asset_id, payload)


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


async def handle_get_dashboard(ctx: MemberContext, db: AsyncSession) -> AssetDashboardResponse:
    return await get_dashboard(db, ctx)


async def handle_get_meta(ctx: MemberContext, db: AsyncSession) -> AssetMetaResponse:
    return await get_asset_meta(db, ctx)


async def handle_export_report(ctx: MemberContext, db: AsyncSession, payload: AssetReportRequest) -> str:
    return await export_asset_report(db, ctx, payload)


async def handle_export_report_pdf(ctx: MemberContext, db: AsyncSession, payload: AssetReportRequest) -> bytes:
    return await export_asset_report_pdf(db, ctx, payload)


# ── Asset ID CRUD handlers ────────────────────────────────────────────────────

async def handle_create_asset_id(
    ctx: MemberContext, db: AsyncSession, payload: AssetIdCreate,
) -> AssetIdResponse:
    return await create_asset_id(db, ctx, payload)

async def handle_list_asset_ids(
    ctx: MemberContext, db: AsyncSession,
) -> list[AssetIdResponse]:
    return await list_asset_ids(db, ctx)

async def handle_update_asset_id(
    ctx: MemberContext, db: AsyncSession, asset_id_id: str, payload: AssetIdUpdate,
) -> AssetIdResponse:
    return await update_asset_id(db, ctx, asset_id_id, payload)

async def handle_delete_asset_id(
    ctx: MemberContext, db: AsyncSession, asset_id_id: str,
) -> None:
    await delete_asset_id(db, ctx, asset_id_id)


# ── Category CRUD handlers ─────────────────────────────────────────────────────


async def handle_create_category(
    ctx: MemberContext,
    db: AsyncSession,
    payload: AssetCategoryCreate,
) -> AssetCategoryResponse:
    return await create_category(db, ctx, payload)


async def handle_list_categories(ctx: MemberContext, db: AsyncSession) -> list[AssetCategoryResponse]:
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
