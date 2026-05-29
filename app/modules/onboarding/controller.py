from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.onboarding import service
from app.modules.onboarding.schema import (
    AcceptedOnboardingWorkspaceRead,
    OnboardingAssignCredentialsRequest,
    OnboardingAssignCredentialsResponse,
    OnboardingSendRequest,
    OnboardingSendResponse,
    OnboardWorkspaceRead,
)
from app.shared.deps.organization_member import MemberContext


async def handle_get_accepted_workspace(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
) -> AcceptedOnboardingWorkspaceRead:
    return await service.get_accepted_workspace(db, ctx.organization.id, job_slug, stage_slug)


async def handle_send_document_requests(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
    body: OnboardingSendRequest,
    background_tasks: BackgroundTasks,
) -> OnboardingSendResponse:
    return await service.send_document_requests(
        db, ctx.organization.id, ctx.member.id, job_slug, stage_slug, body, background_tasks,
    )


async def handle_get_onboard_workspace(
    ctx: MemberContext,
    db: AsyncSession,
    job_slug: str,
    stage_slug: str,
) -> OnboardWorkspaceRead:
    return await service.get_onboard_workspace(db, ctx.organization.id, job_slug, stage_slug)


async def handle_assign_credentials(
    ctx: MemberContext,
    db: AsyncSession,
    record_id: str,
    body: OnboardingAssignCredentialsRequest,
) -> OnboardingAssignCredentialsResponse:
    return await service.assign_credentials(db, ctx.organization.id, record_id, body)


async def handle_confirm_and_send_credentials(
    ctx: MemberContext,
    db: AsyncSession,
    record_id: str,
) -> dict[str, str]:
    return await service.confirm_and_send_credentials(db, ctx.organization.id, record_id)


async def handle_confirm_assign_credentials(
    ctx: MemberContext,
    db: AsyncSession,
    record_id: str,
) -> dict[str, str]:
    return await service.confirm_assign_credentials(db, ctx.organization.id, record_id)


async def handle_send_credentials_with_password(
    ctx: MemberContext,
    db: AsyncSession,
    record_id: str,
    body: dict[str, str],
) -> dict[str, str]:
    return await service.confirm_and_send_credentials_with_password(
        db, ctx.organization.id, record_id, body.get("password", ""),
    )
