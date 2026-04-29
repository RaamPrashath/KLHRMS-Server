"""
Tenant context helpers.
Ensures every DB query is scoped to the authenticated organization.
"""
import uuid
from typing import Annotated

from fastapi import Depends

from app.api.deps.auth import AuthContextDep
from app.schemas.auth_context import AuthContext


def get_organization_id(auth: AuthContextDep) -> uuid.UUID:
    """Extract organization_id from the resolved auth context."""
    return auth.organization_id


OrganizationIdDep = Annotated[uuid.UUID, Depends(get_organization_id)]
