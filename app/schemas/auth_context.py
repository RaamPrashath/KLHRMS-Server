"""
Auth context injected into every protected endpoint.
FastAPI reads the Better Auth session token, verifies it,
then resolves the HRMS role from the DB.
No login/register here — that is Better Auth's job.
"""
import uuid
from dataclasses import dataclass, field


@dataclass
class AuthContext:
    """Resolved identity for the current request."""

    # Better Auth user ID (string UUID from Better Auth users table)
    user_id: str

    # Organization the request is scoped to
    organization_id: uuid.UUID

    # HRMS role resolved from hrms_roles table
    role: str

    # Fine-grained permissions map loaded from hrms_roles.permissions
    permissions: dict[str, bool] = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        return self.permissions.get(permission, False)

    def is_role(self, *roles: str) -> bool:
        return self.role in roles
