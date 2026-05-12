from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.member import Member
from app.models.recruitment import HiringTeam, HiringTeamMember
from app.models.user import User


class HiringTeamRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_teams_for_job(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> list[HiringTeam]:
        result = await self.db.execute(
            select(HiringTeam)
            .options(joinedload(HiringTeam.members).joinedload(HiringTeamMember.member).joinedload(Member.user))
            .where(
                HiringTeam.organizationId == organization_id,
                HiringTeam.jobPostingId == job_posting_id,
                HiringTeam.isActive.is_(True),
            )
            .order_by(HiringTeam.createdAt.desc())
        )
        return list(result.unique().scalars().all())

    async def get_team(
        self,
        organization_id: str,
        team_id: str,
    ) -> HiringTeam | None:
        result = await self.db.execute(
            select(HiringTeam)
            .options(joinedload(HiringTeam.members).joinedload(HiringTeamMember.member).joinedload(Member.user))
            .where(
                HiringTeam.organizationId == organization_id,
                HiringTeam.id == team_id,
            )
        )
        return result.unique().scalar_one_or_none()

    async def get_team_by_job_and_name(
        self,
        organization_id: str,
        job_posting_id: str,
        name: str,
    ) -> HiringTeam | None:
        result = await self.db.execute(
            select(HiringTeam)
            .options(joinedload(HiringTeam.members).joinedload(HiringTeamMember.member).joinedload(Member.user))
            .where(
                HiringTeam.organizationId == organization_id,
                HiringTeam.jobPostingId == job_posting_id,
                HiringTeam.name == name,
                HiringTeam.isActive.is_(True),
            )
        )
        return result.unique().scalar_one_or_none()

    async def add_team(self, team: HiringTeam) -> HiringTeam:
        self.db.add(team)
        await self.db.flush()
        return team

    async def add_team_member(self, team_member: HiringTeamMember) -> HiringTeamMember:
        self.db.add(team_member)
        await self.db.flush()
        return team_member

    async def remove_team_member(
        self,
        organization_id: str,
        team_id: str,
        member_id: str,
    ) -> None:
        result = await self.db.execute(
            select(HiringTeamMember)
            .join(HiringTeam, HiringTeamMember.hiringTeamId == HiringTeam.id)
            .where(
                HiringTeam.organizationId == organization_id,
                HiringTeamMember.hiringTeamId == team_id,
                HiringTeamMember.memberId == member_id,
            )
        )
        team_member = result.scalar_one_or_none()
        if team_member is not None:
            await self.db.delete(team_member)
            await self.db.flush()

    async def count_teams_for_job(
        self,
        organization_id: str,
        job_posting_id: str,
    ) -> int:
        result = await self.db.execute(
            select(func.count(HiringTeam.id)).where(
                HiringTeam.organizationId == organization_id,
                HiringTeam.jobPostingId == job_posting_id,
                HiringTeam.isActive.is_(True),
            )
        )
        return int(result.scalar_one())

    async def get_member(
        self,
        organization_id: str,
        member_id: str,
    ) -> Member | None:
        result = await self.db.execute(
            select(Member)
            .options(joinedload(Member.user))
            .where(
                Member.organizationId == organization_id,
                Member.id == member_id,
            )
        )
        return result.scalar_one_or_none()
