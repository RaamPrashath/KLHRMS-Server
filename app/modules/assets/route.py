from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assets.controller import (
    handle_create_asset,
    handle_create_asset_id,
    handle_create_category,
    handle_create_category_field,
    handle_create_maintenance,
    handle_delete_asset,
    handle_delete_category,
    handle_delete_category_field,
    handle_export_report,
    handle_export_report_pdf,
    handle_get_asset,
    handle_get_dashboard,
    handle_get_meta,
    handle_list_asset_ids,
    handle_list_assets,
    handle_list_categories,
    handle_provide_asset,
    handle_return_asset,
    handle_update_asset,
    handle_update_asset_id,
    handle_delete_asset_id,
    handle_update_category,
    handle_update_category_field,
    handle_update_maintenance,
)
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
    page_size: int = Query(default=20, ge=1, le=100),
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
    access: Annotated[MemberContext, Depends(require_permission("assets", "view", allow_self=True))],
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
    access: Annotated[MemberContext, Depends(require_permission("assets", "view", allow_self=True))],
    db: DbSession,
) -> list[AssetCategoryResponse]:
    return await handle_list_categories(access, db)


@router.post("/categories", response_model=AssetCategoryResponse, status_code=status.HTTP_201_CREATED)
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


@router.post("/categories/{category_id}/fields", response_model=CategoryFieldDefinitionResponse, status_code=status.HTTP_201_CREATED)
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
    access: Annotated[MemberContext, Depends(require_permission("assets", "view", allow_self=True))],
    db: DbSession,
) -> AssetListResponse:
    return await handle_list_assets(access, db, filters)


@router.get("/dashboard", response_model=AssetDashboardResponse)
async def get_asset_dashboard(
    access: Annotated[MemberContext, Depends(require_permission("assets", "view", allow_self=True))],
    db: DbSession,
) -> AssetDashboardResponse:
    return await handle_get_dashboard(access, db)


@router.get("/meta", response_model=AssetMetaResponse)
async def get_asset_meta(
    access: Annotated[MemberContext, Depends(require_permission("assets", "view", allow_self=True))],
    db: DbSession,
) -> AssetMetaResponse:
    return await handle_get_meta(access, db)


@router.get("/report.csv")
async def export_asset_report_route(
    access: Annotated[MemberContext, Depends(require_permission("assets", "view", allow_self=True))],
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
    access: Annotated[MemberContext, Depends(require_permission("assets", "view", allow_self=True))],
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


@router.get("/{asset_id}", response_model=AssetDetailResponse)
async def get_asset_detail(
    asset_id: str,
    access: Annotated[MemberContext, Depends(require_permission("assets", "view", allow_self=True))],
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


@router.post("/{asset_id}/provide", response_model=AssetDetailResponse)
async def provide_asset_route(
    asset_id: str,
    body: AssetProvideRequest,
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
    db: DbSession,
) -> AssetDetailResponse:
    return await handle_provide_asset(access, db, asset_id, body)


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
    access: Annotated[MemberContext, Depends(require_permission("assets", "edit"))],
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
