"""Employee endpoints — placeholder for service wiring."""
from fastapi import APIRouter

from app.api.deps.auth import AuthContextDep

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("")
async def list_employees(auth: AuthContextDep):
    # TODO: wire EmployeeService
    raise NotImplementedError


@router.post("", status_code=201)
async def create_employee(auth: AuthContextDep):
    raise NotImplementedError


@router.get("/{employee_id}")
async def get_employee(employee_id: str, auth: AuthContextDep):
    raise NotImplementedError


@router.patch("/{employee_id}")
async def update_employee(employee_id: str, auth: AuthContextDep):
    raise NotImplementedError


@router.delete("/{employee_id}", status_code=204)
async def delete_employee(employee_id: str, auth: AuthContextDep):
    raise NotImplementedError
