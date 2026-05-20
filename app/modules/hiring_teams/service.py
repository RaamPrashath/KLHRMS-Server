from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recruitment import HiringTeam, HiringTeamMember
from app.modules.hiring_teams.repository import HiringTeamRepository
from app.modules.hiring_teams.schema import (
    HiringTeamCreateRequest,
    HiringTeamListResponse,
    HiringTeamMemberAddRequest,
    HiringTeamMemberRead,
    HiringTeamRead,
    HiringTeamUpdateRequest,
)
from app.shared.deps.organization_member import MemberContext


def _member_name(member) -> str | None:
    if member is None or member.user is None:
        return None
    return member.user.name or member.user.email


def _serialize_team_member(team_member: HiringTeamMember) -> HiringTeamMemberRead:
    member = team_member.member
    return HiringTeamMemberRead(
        id=team_member.id,
        memberId=team_member.memberId,
        name=_member_name(member),
        email=member.user.email if member and member.user else None,
        role=team_member.role,
    )


def _serialize_team(team: HiringTeam) -> HiringTeamRead:
    return HiringTeamRead(
        id=team.id,
        jobPostingId=team.jobPostingId,
        stageId=team.stageId,
        name=team.name,
        description=team.description,
        isActive=team.isActive,
        memberCount=len(team.members or []),
        members=[_serialize_team_member(item) for item in (team.members or [])],
        createdAt=team.createdAt,
        updatedAt=team.updatedAt,
    )


async def list_teams_for_job(
    db: AsyncSession,
    organization_id: str,
    job_posting_id: str,
    stage_id: str | None = None,
) -> HiringTeamListResponse:
    repository = HiringTeamRepository(db)
    teams = await repository.list_teams_for_job(organization_id, job_posting_id, stage_id=stage_id)
    return HiringTeamListResponse(
        items=[_serialize_team(team) for team in teams],
        total=len(teams),
    )


async def get_team(
    db: AsyncSession,
    organization_id: str,
    team_id: str,
) -> HiringTeamRead:
    repository = HiringTeamRepository(db)
    team = await repository.get_team(organization_id, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Hiring team not found")
    return _serialize_team(team)


async def create_team(
    db: AsyncSession,
    organization_id: str,
    body: HiringTeamCreateRequest,
) -> HiringTeamRead:
    repository = HiringTeamRepository(db)
    normalized_name = body.name.strip()

    # Validate all member IDs belong to the organization
    member_ids = [item.memberId for item in body.members]
    if member_ids:
        members = await repository.get_member(organization_id, member_ids[0])
        # naive check; we should check all. Let's do it properly.
    # Actually let's check each member
    seen = set()
    for item in body.members:
        if item.memberId in seen:
            raise HTTPException(status_code=400, detail="Duplicate member in team")
        seen.add(item.memberId)
        member = await repository.get_member(organization_id, item.memberId)
        if member is None:
            raise HTTPException(status_code=400, detail=f"Member {item.memberId} not found")

    existing_team = await repository.get_team_by_job_and_name(
        organization_id,
        body.jobPostingId,
        normalized_name,
        stage_id=body.stageId,
    )
    if existing_team is not None:
        existing_member_ids = sorted(item.memberId for item in (existing_team.members or []))
        requested_member_ids = sorted(item.memberId for item in body.members)
        if existing_member_ids == requested_member_ids:
            return _serialize_team(existing_team)
        # Team exists with different members — replace them
        for item in body.members:
            if item.memberId not in existing_member_ids:
                team_member = HiringTeamMember(
                    hiringTeamId=existing_team.id,
                    memberId=item.memberId,
                    role=item.role,
                )
                await repository.add_team_member(team_member)
        for item in (existing_team.members or []):
            if item.memberId not in requested_member_ids:
                await repository.remove_team_member(organization_id, existing_team.id, item.memberId)
        await db.commit()
        refreshed = await repository.get_team(organization_id, existing_team.id)
        return _serialize_team(refreshed)

    team = HiringTeam(
        organizationId=organization_id,
        jobPostingId=body.jobPostingId,
        name=normalized_name,
        description=body.description.strip() if body.description else None,
        stageId=body.stageId,
        isActive=True,
    )
    try:
        await repository.add_team(team)

        for item in body.members:
            team_member = HiringTeamMember(
                hiringTeamId=team.id,
                memberId=item.memberId,
                role=item.role,
            )
            await repository.add_team_member(team_member)

        await db.commit()
    except IntegrityError:
        await db.rollback()
        # Race condition: another create won. Find it and replace members.
        conflict = await repository.get_team_by_job_and_name(
            organization_id,
            body.jobPostingId,
            normalized_name,
            stage_id=body.stageId,
        )
        if conflict is not None:
            for item in body.members:
                if item.memberId not in {m.memberId for m in (conflict.members or [])}:
                    await repository.add_team_member(HiringTeamMember(
                        hiringTeamId=conflict.id,
                        memberId=item.memberId,
                        role=item.role,
                    ))
            for item in (conflict.members or []):
                if item.memberId not in {m.memberId for m in body.members}:
                    await repository.remove_team_member(organization_id, conflict.id, item.memberId)
            await db.commit()
            refreshed = await repository.get_team(organization_id, conflict.id)
            return _serialize_team(refreshed)
        raise HTTPException(status_code=409, detail="Conflict creating hiring team")
    refreshed = await repository.get_team(organization_id, team.id)
    return _serialize_team(refreshed)


async def update_team(
    db: AsyncSession,
    organization_id: str,
    team_id: str,
    body: HiringTeamUpdateRequest,
) -> HiringTeamRead:
    repository = HiringTeamRepository(db)
    team = await repository.get_team(organization_id, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Hiring team not found")

    if body.name is not None:
        team.name = body.name.strip()
    if body.description is not None:
        team.description = body.description.strip() if body.description.strip() else None
    if body.isActive is not None:
        team.isActive = body.isActive

    db.add(team)
    await db.commit()
    refreshed = await repository.get_team(organization_id, team_id)
    return _serialize_team(refreshed)


async def delete_team(
    db: AsyncSession,
    organization_id: str,
    team_id: str,
) -> None:
    repository = HiringTeamRepository(db)
    team = await repository.get_team(organization_id, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Hiring team not found")
    team.isActive = False
    db.add(team)
    await db.commit()


async def add_team_member(
    db: AsyncSession,
    organization_id: str,
    team_id: str,
    body: HiringTeamMemberAddRequest,
) -> HiringTeamRead:
    repository = HiringTeamRepository(db)
    team = await repository.get_team(organization_id, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Hiring team not found")

    member = await repository.get_member(organization_id, body.memberId)
    if member is None:
        raise HTTPException(status_code=400, detail="Member not found")

    existing_ids = {item.memberId for item in (team.members or [])}
    if body.memberId in existing_ids:
        raise HTTPException(status_code=400, detail="Member already in team")

    team_member = HiringTeamMember(
        hiringTeamId=team_id,
        memberId=body.memberId,
        role=body.role,
    )
    await repository.add_team_member(team_member)
    await db.commit()
    refreshed = await repository.get_team(organization_id, team_id)
    return _serialize_team(refreshed)


async def remove_team_member(
    db: AsyncSession,
    organization_id: str,
    team_id: str,
    member_id: str,
) -> HiringTeamRead:
    repository = HiringTeamRepository(db)
    team = await repository.get_team(organization_id, team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Hiring team not found")

    await repository.remove_team_member(organization_id, team_id, member_id)
    await db.commit()
    refreshed = await repository.get_team(organization_id, team_id)
    return _serialize_team(refreshed)
