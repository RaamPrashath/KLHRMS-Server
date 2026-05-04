"""
Role service — pure database operations, all scoped by organizationId.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.base import generate_uuid
from app.models.role import Role
from app.modules.role.schema import RoleCreateRequest, RoleUpdateRequest


def get_role_by_id(db: Session, organization_id: str, role_id: str) -> Role:
    """
    Fetch a role by id, scoped to the given organization.
    Raises 404 if not found.
    """
    role: Role | None = (
        db.query(Role)
        .filter(Role.id == role_id, Role.organizationId == organization_id)
        .first()
    )
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def list_roles(db: Session, organization_id: str) -> list[Role]:
    """
    Return all roles for the given organization, ordered by createdAt ascending.
    """
    return (
        db.query(Role)
        .filter(Role.organizationId == organization_id)
        .order_by(Role.createdAt.asc())
        .all()
    )


def create_role(
    db: Session,
    organization_id: str,
    data: RoleCreateRequest,
) -> Role:
    """
    Insert a new Role record.
    Raises 409 if a role with the same name already exists in the organization.
    """
    existing: Role | None = (
        db.query(Role)
        .filter(
            Role.organizationId == organization_id,
            Role.name == data.name,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="A role with this name already exists in the organization",
        )

    role = Role(
        id=generate_uuid(),
        organizationId=organization_id,
        name=data.name,
        permissions=data.permissions,
    )
    db.add(role)
    try:
        db.commit()
        db.refresh(role)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A role with this name already exists in the organization",
        )
    return role


def update_role(
    db: Session,
    organization_id: str,
    role_id: str,
    data: RoleUpdateRequest,
) -> Role:
    """
    Apply a partial update to an existing role.
    Raises 404 if the role does not exist in the organization.
    Raises 409 on name conflict within the same organization.
    """
    role = get_role_by_id(db, organization_id, role_id)

    if data.name is not None:
        role.name = data.name
    if data.permissions is not None:
        role.permissions = data.permissions

    try:
        db.commit()
        db.refresh(role)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A role with this name already exists in the organization",
        )
    return role


def delete_role(db: Session, organization_id: str, role_id: str) -> None:
    """
    Delete a role by id, scoped to the given organization.
    Raises 404 if the role does not exist.
    """
    role = get_role_by_id(db, organization_id, role_id)
    db.delete(role)
    db.commit()
