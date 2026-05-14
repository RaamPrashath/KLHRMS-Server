from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hiring_teams.controller import (
    handle_add_team_member,
    handle_create_team,
    handle_delete_team,
    handle_get_team,
    handle_list_teams,
    handle_remove_team_member,
    handle_update_team,
)
from app.modules.hiring_teams.schema import (
    HiringTeamCreateRequest,
    HiringTeamListResponse,
    HiringTeamMemberAddRequest,
    HiringTeamRead,
    HiringTeamUpdateRequest,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/hiring-teams", tags=["hiring-teams"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=HiringTeamListResponse)
async def list_teams(
    access: Annotated[MemberContext, Depends(require_permission("interviews", "view"))],
    db: DbSession,
    jobPostingId: str = Query(..., min_length=1),
) -> HiringTeamListResponse:
    return await handle_list_teams(access, db, jobPostingId)


@router.post("", response_model=HiringTeamRead, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: HiringTeamCreateRequest,
    access: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: DbSession,
) -> HiringTeamRead:
    return await handle_create_team(access, db, body)


@router.get("/{team_id}", response_model=HiringTeamRead)
async def get_team(
    team_id: str,
    access: Annotated[MemberContext, Depends(require_permission("interviews", "view"))],
    db: DbSession,
) -> HiringTeamRead:
    return await handle_get_team(access, db, team_id)


@router.patch("/{team_id}", response_model=HiringTeamRead)
async def update_team(
    team_id: str,
    body: HiringTeamUpdateRequest,
    access: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: DbSession,
) -> HiringTeamRead:
    return await handle_update_team(access, db, team_id, body)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: str,
    access: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: DbSession,
) -> Response:
    await handle_delete_team(access, db, team_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{team_id}/members", response_model=HiringTeamRead)
async def add_team_member(
    team_id: str,
    body: HiringTeamMemberAddRequest,
    access: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: DbSession,
) -> HiringTeamRead:
    return await handle_add_team_member(access, db, team_id, body)


@router.delete("/{team_id}/members/{member_id}", response_model=HiringTeamRead)
async def remove_team_member(
    team_id: str,
    member_id: str,
    access: Annotated[MemberContext, Depends(require_permission("interviews", "edit"))],
    db: DbSession,
) -> HiringTeamRead:
    return await handle_remove_team_member(access, db, team_id, member_id)
