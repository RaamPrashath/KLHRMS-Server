from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assets.schema import (
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
)
from app.modules.assets.service import (
    create_maintenance_record,
    delete_asset,
    export_asset_report,
    export_asset_report_pdf,
    get_asset,
    get_asset_meta,
    list_assets,
    provide_asset,
    return_asset,
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


async def handle_get_meta(ctx: MemberContext, db: AsyncSession) -> AssetMetaResponse:
    return await get_asset_meta(db, ctx)


async def handle_export_report(ctx: MemberContext, db: AsyncSession, payload: AssetReportRequest) -> str:
    return await export_asset_report(db, ctx, payload)


async def handle_export_report_pdf(ctx: MemberContext, db: AsyncSession, payload: AssetReportRequest) -> bytes:
    return await export_asset_report_pdf(db, ctx, payload)
