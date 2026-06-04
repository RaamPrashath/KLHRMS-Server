import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.microsoft_graph.exceptions import MicrosoftGraphConfigurationError
from app.integrations.microsoft_graph.schema import ConnectionTestResult, MicrosoftOrganization
from app.modules.microsoft_graph.controller import MicrosoftGraphController
from app.modules.microsoft_graph.schema import (
    MicrosoftSettingsResponse,
    SyncRunListItem,
    SyncRunResponse,
    SyncStatusResponse,
    TestConnectionRequest,
)
from app.modules.microsoft_graph.service import MicrosoftIntegrationService
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_any_permission

logger = logging.getLogger("klhrms.microsoft.graph.route")

router = APIRouter(prefix="/microsoft-graph", tags=["Microsoft Graph"])

ORG_EDIT = require_any_permission(("organization", "edit"), ("employees", "edit"))


def _get_controller(db: AsyncSession) -> MicrosoftGraphController:
    service = MicrosoftIntegrationService(db)
    return MicrosoftGraphController(service)


@router.get("/settings", response_model=MicrosoftSettingsResponse)
async def get_settings(
    ctx: Annotated[MemberContext, Depends(ORG_EDIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    controller = _get_controller(db)
    return await controller.get_settings(str(ctx.organization.id))


@router.put("/settings", response_model=MicrosoftSettingsResponse)
async def save_settings(
    ctx: Annotated[MemberContext, Depends(ORG_EDIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: TestConnectionRequest,
):
    try:
        controller = _get_controller(db)
        return await controller.save_settings(
            str(ctx.organization.id), body.tenant_id, body.client_id, body.client_secret
        )
    except MicrosoftGraphConfigurationError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/test-connection", response_model=ConnectionTestResult)
async def test_connection(
    ctx: Annotated[MemberContext, Depends(ORG_EDIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body: TestConnectionRequest | None = None,
):
    try:
        controller = _get_controller(db)
        return await controller.test_connection(
            str(ctx.organization.id),
            body.tenant_id if body else "",
            body.client_id if body else "",
            body.client_secret if body else "",
        )
    except MicrosoftGraphConfigurationError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/organization", response_model=MicrosoftOrganization)
async def get_organization(
    ctx: Annotated[MemberContext, Depends(ORG_EDIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    controller = _get_controller(db)
    return await controller.get_organization(str(ctx.organization.id))


@router.post("/sync", response_model=SyncRunResponse)
async def sync_employees(
    ctx: Annotated[MemberContext, Depends(ORG_EDIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        controller = _get_controller(db)
        return await controller.sync_employees(
            str(ctx.organization.id), ctx.member.id
        )
    except MicrosoftGraphConfigurationError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/sync-status", response_model=SyncStatusResponse)
async def get_sync_status(
    ctx: Annotated[MemberContext, Depends(ORG_EDIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    controller = _get_controller(db)
    return await controller.get_sync_status(str(ctx.organization.id))


@router.get("/profile-photos/{org_id}/{microsoft_id}", include_in_schema=False)
async def get_profile_photo(
    org_id: str,
    microsoft_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    service = MicrosoftIntegrationService(db)
    photo = await service.get_profile_photo_bytes(org_id, microsoft_id)
    if photo is None:
        raise HTTPException(404, "Profile photo not found")
    return Response(content=photo, media_type="image/jpeg")


@router.get("/sync-runs", response_model=list[SyncRunListItem])
async def get_sync_runs(
    ctx: Annotated[MemberContext, Depends(ORG_EDIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
    offset: int = 0,
):
    controller = _get_controller(db)
    return await controller.get_sync_runs(str(ctx.organization.id), limit, offset)


@router.get("/sync-runs/{run_id}", response_model=SyncRunResponse)
async def get_sync_run(
    run_id: str,
    ctx: Annotated[MemberContext, Depends(ORG_EDIT)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    controller = _get_controller(db)
    result = await controller.get_sync_run(str(ctx.organization.id), run_id)
    if not result:
        raise HTTPException(404, "Sync run not found")
    return result
