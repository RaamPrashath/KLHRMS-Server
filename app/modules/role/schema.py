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
  none < self < team < department < organization

Standard actions:
  view, create, edit, delete

Domain-specific actions (per module):
  leaves.approve
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Permissions type alias
# ---------------------------------------------------------------------------

# The permissions dict has the shape:
#   { module: { action: scope } }
# e.g. { "attendance": { "view": "organization", "create": "self", "edit": "self", "delete": "none" } }
PermissionsDict = dict[str, dict[str, str]]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    permissions: PermissionsDict


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    permissions: PermissionsDict | None = None

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
