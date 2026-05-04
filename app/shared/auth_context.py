"""
Auth context — resolved identity injected into every protected endpoint.
Populated by the auth dependency after verifying the Better Auth session token.
"""
import uuid
from dataclasses import dataclass, field


@dataclass
class AuthContext:
    user_id: str                          # Better Auth user ID
    organization_id: uuid.UUID            # Verified org — use for all DB queries
    role: str                             # One of the ROLE_* constants
    permissions: dict[str, bool] = field(default_factory=dict)

    def has_permission(self, permission: str) -> bool:
        return self.permissions.get(permission, False)

    def is_role(self, *roles: str) -> bool:
        return self.role in roles
