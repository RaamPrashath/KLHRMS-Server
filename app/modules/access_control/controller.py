from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.access_control.service import (
    list_logs as _list_logs,
    get_log_summary as _get_log_summary,
    create_log as _create_log,
    update_log as _update_log,
    bulk_import_logs as _bulk_import_logs,
    list_assignments as _list_assignments,
    create_assignment as _create_assignment,
    update_assignment as _update_assignment,
)
from app.shared.deps.organization_member import MemberContext


async def handle_list_logs(
    ctx: MemberContext,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    employee_member_id: str | None = None,
    access_point: str | None = None,
    status: str | None = None,
    direction: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    return await _list_logs(
        db, ctx, page, page_size, employee_member_id, access_point,
        status, direction, date_from, date_to,
    )


async def handle_get_log_summary(
    ctx: MemberContext,
    db: AsyncSession,
) -> dict:
    return await _get_log_summary(db, ctx)


async def handle_create_log(
    ctx: MemberContext,
    db: AsyncSession,
    payload: dict,
) -> dict:
    return await _create_log(db, ctx, payload)


async def handle_update_log(
    ctx: MemberContext,
    db: AsyncSession,
    log_id: str,
    payload: dict,
) -> dict:
    return await _update_log(db, ctx, log_id, payload)


async def handle_bulk_import_logs(
    ctx: MemberContext,
    db: AsyncSession,
    logs: list[dict],
) -> dict:
    return await _bulk_import_logs(db, ctx, logs)


async def handle_list_assignments(
    ctx: MemberContext,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    employee_member_id: str | None = None,
    access_point: str | None = None,
    status: str | None = None,
) -> dict:
    return await _list_assignments(
        db, ctx, page, page_size, employee_member_id, access_point, status,
    )


async def handle_create_assignment(
    ctx: MemberContext,
    db: AsyncSession,
    payload: dict,
) -> dict:
    return await _create_assignment(db, ctx, payload)


async def handle_update_assignment(
    ctx: MemberContext,
    db: AsyncSession,
    assignment_id: str,
    payload: dict,
) -> dict:
    return await _update_assignment(db, ctx, assignment_id, payload)
