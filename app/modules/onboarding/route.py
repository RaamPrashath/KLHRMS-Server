from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.onboarding.controller import (
    handle_assign_credentials,
    handle_confirm_and_send_credentials,
    handle_confirm_assign_credentials,
    handle_get_accepted_workspace,
    handle_get_onboard_workspace,
    handle_send_document_requests,
    handle_send_credentials_with_password,
)
from app.modules.onboarding.schema import (
    AcceptedOnboardingWorkspaceRead,
    OnboardingAssignCredentialsRequest,
    OnboardingAssignCredentialsResponse,
    OnboardingSendRequest,
    OnboardingSendResponse,
    OnboardWorkspaceRead,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext, get_member_context
from app.shared.deps.permissions import require_permission
from app.shared.utils.permissions import get_member_permission_scope

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def require_any_candidate_permission(*actions: str) -> Callable[..., MemberContext]:
    def _dependency(ctx: MemberContext = Depends(get_member_context)) -> MemberContext:
        for action in actions:
            if get_member_permission_scope(ctx.member, "candidates", action) == "organization":
                ctx.scope = "organization"
                return ctx
        raise HTTPException(status_code=403, detail="you dont have permission")
    _dependency.__name__ = f"require_any_candidate_{'_'.join(actions)}"
    return _dependency


OnboardingManageCtx = Annotated[
    MemberContext,
    Depends(require_any_candidate_permission("view", "create", "edit", "delete")),
]
OnboardingViewCtx = Annotated[MemberContext, Depends(require_permission("candidates", "view"))]


@router.get(
    "/pipeline/jobs/{job_slug}/stages/{stage_slug}/workspace",
    response_model=AcceptedOnboardingWorkspaceRead,
)
async def get_accepted_workspace(
    job_slug: str,
    stage_slug: str,
    ctx: OnboardingViewCtx,
    db: AsyncSession = Depends(get_db),
) -> AcceptedOnboardingWorkspaceRead:
    return await handle_get_accepted_workspace(ctx, db, job_slug, stage_slug)


@router.post(
    "/pipeline/jobs/{job_slug}/stages/{stage_slug}/send-requests",
    response_model=OnboardingSendResponse,
)
async def send_onboarding_requests(
    job_slug: str,
    stage_slug: str,
    body: OnboardingSendRequest,
    background_tasks: BackgroundTasks,
    ctx: OnboardingManageCtx,
    db: AsyncSession = Depends(get_db),
) -> OnboardingSendResponse:
    return await handle_send_document_requests(ctx, db, job_slug, stage_slug, body, background_tasks)


@router.get(
    "/pipeline/jobs/{job_slug}/stages/{stage_slug}/onboard-workspace",
    response_model=OnboardWorkspaceRead,
)
async def get_onboard_workspace(
    job_slug: str,
    stage_slug: str,
    ctx: OnboardingViewCtx,
    db: AsyncSession = Depends(get_db),
) -> OnboardWorkspaceRead:
    return await handle_get_onboard_workspace(ctx, db, job_slug, stage_slug)


@router.post(
    "/records/{record_id}/assign",
    response_model=OnboardingAssignCredentialsResponse,
)
async def assign_credentials(
    record_id: str,
    body: OnboardingAssignCredentialsRequest,
    ctx: OnboardingManageCtx,
    db: AsyncSession = Depends(get_db),
) -> OnboardingAssignCredentialsResponse:
    return await handle_assign_credentials(ctx, db, record_id, body)


@router.get("/records/{record_id}/provision-password")
async def provision_credentials_password(
    record_id: str,
    ctx: OnboardingManageCtx,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await handle_confirm_assign_credentials(ctx, db, record_id)


@router.post("/records/{record_id}/send-credentials")
async def send_credentials(
    record_id: str,
    body: dict[str, str],
    ctx: OnboardingManageCtx,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    return await handle_send_credentials_with_password(ctx, db, record_id, body)
