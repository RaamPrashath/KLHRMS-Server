from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hiring_teams import service
from app.modules.hiring_teams.schema import (
    HiringTeamCreateRequest,
    HiringTeamListResponse,
    HiringTeamMemberAddRequest,
    HiringTeamRead,
    HiringTeamUpdateRequest,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_teams(
    ctx: MemberContext,
    db: AsyncSession,
    job_posting_id: str,
) -> HiringTeamListResponse:
    return await service.list_teams_for_job(db, ctx.organization.id, job_posting_id)


async def handle_get_team(
    ctx: MemberContext,
    db: AsyncSession,
    team_id: str,
) -> HiringTeamRead:
    return await service.get_team(db, ctx.organization.id, team_id)


async def handle_create_team(
    ctx: MemberContext,
    db: AsyncSession,
    body: HiringTeamCreateRequest,
) -> HiringTeamRead:
    return await service.create_team(db, ctx.organization.id, body)


async def handle_update_team(
    ctx: MemberContext,
    db: AsyncSession,
    team_id: str,
    body: HiringTeamUpdateRequest,
) -> HiringTeamRead:
    return await service.update_team(db, ctx.organization.id, team_id, body)


async def handle_delete_team(
    ctx: MemberContext,
    db: AsyncSession,
    team_id: str,
) -> None:
    await service.delete_team(db, ctx.organization.id, team_id)


async def handle_add_team_member(
    ctx: MemberContext,
    db: AsyncSession,
    team_id: str,
    body: HiringTeamMemberAddRequest,
) -> HiringTeamRead:
    return await service.add_team_member(db, ctx.organization.id, team_id, body)


async def handle_remove_team_member(
    ctx: MemberContext,
    db: AsyncSession,
    team_id: str,
    member_id: str,
) -> HiringTeamRead:
    return await service.remove_team_member(db, ctx.organization.id, team_id, member_id)
