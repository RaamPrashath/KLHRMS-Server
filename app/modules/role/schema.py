"""
Pydantic schemas for the Role module.

Permission JSON structure:
{
  "<module>": {
    "<action>": "<scope>"
  }
}

Example:
{
  "attendance": {
    "view": "organization",
    "create": "self",
    "edit": "self",
    "delete": "none"
  },
  "leaves": {
    "view": "department",
    "create": "self",
    "approve": "organization"
  }
}

Valid scopes (ordered hierarchy):
  none < self < department < organization

Standard actions:
  view, create, edit, delete

Domain-specific actions (per module):
  leaves.approve
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Permissions type alias
# ---------------------------------------------------------------------------

# The permissions dict has the shape:
#   { module: { action: scope } }
# e.g. { "attendance": { "view": "organization", "create": "self", "edit": "self", "delete": "none" } }
PermissionsDict = dict[str, dict[str, str]]
VALID_PERMISSION_SCOPES = {"none", "self", "department", "organization"}


def _validate_permission_scopes(permissions: PermissionsDict | None) -> PermissionsDict | None:
    if permissions is None:
        return None
    for module, actions in permissions.items():
        for action, scope in actions.items():
            if scope not in VALID_PERMISSION_SCOPES:
                raise ValueError(f"Invalid permission scope for {module}.{action}")
    return permissions


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    permissions: PermissionsDict

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: PermissionsDict) -> PermissionsDict:
        return _validate_permission_scopes(value) or value


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    permissions: PermissionsDict | None = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: PermissionsDict | None) -> PermissionsDict | None:
        return _validate_permission_scopes(value)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "RoleUpdateRequest":
        if self.name is None and self.permissions is None:
            raise ValueError("At least one of 'name' or 'permissions' must be provided")
        return self


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class RoleResponse(BaseModel):
    id: str
    organizationId: str
    name: str
    permissions: PermissionsDict
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}
