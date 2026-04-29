"""Project endpoints."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(auth: AuthContextDep):
    raise NotImplementedError


@router.post("", status_code=201)
async def create_project(auth: AuthContextDep):
    raise NotImplementedError


@router.get("/{project_id}")
async def get_project(project_id: str, auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{project_id}")
async def update_project(project_id: str, auth: AuthContextDep):
    raise NotImplementedError
