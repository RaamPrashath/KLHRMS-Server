"""Helpdesk ticket endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/helpdesk", tags=["helpdesk"])


@router.get("")
async def list_tickets(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def create_ticket(auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{ticket_id}")
async def update_ticket(ticket_id: str, auth: AuthContextDep):
    raise NotImplementedError
