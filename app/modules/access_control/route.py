from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access_control.controller import (
    handle_bulk_import_logs,
    handle_create_assignment,
    handle_create_log,
    handle_get_log_summary,
    handle_list_assignments,
    handle_list_logs,
    handle_update_assignment,
    handle_update_log,
)
from app.modules.access_control.schema import (
    AccessControlAssignmentCreate,
    AccessControlAssignmentListResponse,
    AccessControlAssignmentResponse,
    AccessControlAssignmentUpdate,
    AccessControlLogCreate,
    AccessControlLogListResponse,
    AccessControlLogResponse,
    AccessControlLogSummaryResponse,
    AccessControlLogUpdate,
)
from app.shared.database import get_db
from app.shared.deps.organization_member import MemberContext
from app.shared.deps.permissions import require_permission

router = APIRouter(prefix="/access-control", tags=["access-control"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/logs", response_model=AccessControlLogListResponse)
async def list_access_logs(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    employee_member_id: str | None = Query(default=None, alias="employee_member_id"),
    access_point: str | None = Query(default=None, alias="access_point"),
    status: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    date_from: str | None = Query(default=None, alias="date_from"),
    date_to: str | None = Query(default=None, alias="date_to"),
) -> dict:
    return await handle_list_logs(
        access, db, page, page_size, employee_member_id,
        access_point, status, direction, date_from, date_to,
    )


@router.get("/logs/summary", response_model=AccessControlLogSummaryResponse)
async def get_log_summary(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
) -> dict:
    return await handle_get_log_summary(access, db)


@router.post("/logs", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_access_log(
    body: AccessControlLogCreate,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "edit"))
    ],
    db: DbSession,
) -> dict:
    return await handle_create_log(access, db, body.model_dump())


@router.patch("/logs/{log_id}", response_model=dict)
async def update_access_log(
    log_id: str,
    body: AccessControlLogUpdate,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "edit"))
    ],
    db: DbSession,
) -> dict:
    return await handle_update_log(access, db, log_id, body.model_dump(exclude_none=True))


@router.post("/logs/import", response_model=dict, status_code=status.HTTP_201_CREATED)
async def bulk_import_logs(
    logs: list[AccessControlLogCreate],
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "edit"))
    ],
    db: DbSession,
) -> dict:
    return await handle_bulk_import_logs(access, db, [l.model_dump() for l in logs])


@router.get("/assignments", response_model=AccessControlAssignmentListResponse)
async def list_access_assignments(
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "view", allow_self=True))
    ],
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    employee_member_id: str | None = Query(default=None, alias="employee_member_id"),
    access_point: str | None = Query(default=None, alias="access_point"),
    status: str | None = Query(default=None),
) -> dict:
    return await handle_list_assignments(
        access, db, page, page_size, employee_member_id, access_point, status,
    )


@router.post("/assignments", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_access_assignment(
    body: AccessControlAssignmentCreate,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "edit"))
    ],
    db: DbSession,
) -> dict:
    return await handle_create_assignment(access, db, body.model_dump())


@router.patch("/assignments/{assignment_id}", response_model=dict)
async def update_access_assignment(
    assignment_id: str,
    body: AccessControlAssignmentUpdate,
    access: Annotated[
        MemberContext, Depends(require_permission("assets", "edit"))
    ],
    db: DbSession,
) -> dict:
    return await handle_update_assignment(
        access, db, assignment_id, body.model_dump(exclude_none=True),
    )
