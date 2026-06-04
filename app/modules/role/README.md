# Role Module (Backend)

This module implements the backend API for role and permission management in the KL HRMS system.

## Overview

The role module provides CRUD operations for roles, which define what actions members can perform across different HRMS modules. All operations are scoped to an organization and enforce permission checks.

## Architecture

The module follows the standard layered architecture:

```
Route (FastAPI) → Controller → Service → Repository (Prisma)
```

### Layers

- **Route** (`route.py`) — FastAPI endpoints with permission dependencies
- **Controller** (`controller.py`) — Orchestrates service calls and applies self-filtering
- **Service** (`service.py`) — Business logic, all functions are `async`
- **Schema** (`schema.py`) — Pydantic request/response models

## Database Model

```prisma
model Role {
  id             String   @id @default(uuid())
  organizationId String
  name           String
  permissions    Json
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  organization Organization @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  members      Member[]

  @@unique([organizationId, id])
  @@unique([organizationId, name])
  @@index([organizationId])
  @@map("role")
}
```

**Key constraints:**
- Role names must be unique within an organization
- Roles are cascade-deleted when the organization is deleted
- Every role belongs to exactly one organization

## API Endpoints

All endpoints require the following headers:
- `x-organization-slug` — Organization URL slug
- `x-membership-id` — Current member's ID

### List Roles

```http
GET /roles
```

**Permission:** `permission.view` (allows `self` or `organization` scope)

**Behavior:**
- `organization` scope → Returns all roles in the organization
- `self` scope → Returns only the member's own role

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "organizationId": "uuid",
    "name": "HR Manager",
    "permissions": {
      "attendance": { "view": "organization", "create": "self" }
    },
    "createdAt": "2024-01-01T00:00:00Z",
    "updatedAt": "2024-01-01T00:00:00Z"
  }
]
```

### Create Role

```http
POST /roles
```

**Permission:** `permission.create` (requires `organization` scope)

**Request Body:**
```json
{
  "name": "HR Manager",
  "permissions": {
    "attendance": { "view": "organization", "create": "self" },
    "leaves": { "view": "department", "approve": "organization" }
  }
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "organizationId": "uuid",
  "name": "HR Manager",
  "permissions": { ... },
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-01T00:00:00Z"
}
```

**Errors:**
- `409 Conflict` — Role name already exists in the organization
- `403 Forbidden` — No permission to create roles

### Update Role

```http
PATCH /roles/{role_id}
```

**Permission:** `permission.edit` (requires `organization` scope)

**Request Body:** (all fields optional, but at least one required)
```json
{
  "name": "Senior HR Manager",
  "permissions": {
    "attendance": { "view": "organization", "create": "organization" }
  }
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "organizationId": "uuid",
  "name": "Senior HR Manager",
  "permissions": { ... },
  "createdAt": "2024-01-01T00:00:00Z",
  "updatedAt": "2024-01-02T00:00:00Z"
}
```

**Errors:**
- `404 Not Found` — Role doesn't exist in the organization
- `409 Conflict` — New name conflicts with existing role
- `403 Forbidden` — No permission to edit roles

### Delete Role

```http
DELETE /roles/{role_id}
```

**Permission:** `permission.delete` (requires `organization` scope)

**Response:** `204 No Content`

**Errors:**
- `404 Not Found` — Role doesn't exist in the organization
- `403 Forbidden` — No permission to delete roles

## Permission Enforcement

All endpoints use the `require_permission` dependency factory:

```python
from app.shared.deps.permissions import require_permission

@router.get("", response_model=list[RoleResponse])
async def list_roles(
    ctx: Annotated[MemberContext, Depends(require_permission("permission", "view", allow_self=True))],
    db: AsyncSession = Depends(get_db),
):
    return await handle_list_roles(ctx, db)
```

### Parameters

- `module` — The HRMS module key (always `"permission"` for this module)
- `action` — The action being performed (`view`, `create`, `edit`, `delete`)
- `allow_self` — Whether to accept `"self"` scope in addition to `"organization"`

### How It Works

1. The dependency reads `x-organization-slug` and `x-membership-id` headers
2. Resolves the organization and member from the database
3. Reads the member's role permissions JSON
4. Checks if the member has the required `module.action` permission
5. Validates the scope is in the accepted set
6. Attaches the resolved scope to the context as `ctx.scope`
7. Raises `403 Forbidden` if any check fails

## Self-Filtering

When `allow_self=True`, the controller must apply self-filtering based on `ctx.scope`:

```python
async def handle_list_roles(ctx: MemberContext, db: AsyncSession) -> list[RoleResponse]:
    scope = getattr(ctx, "scope", "organization")

    if scope == "self":
        # Member can only see their own role
        if ctx.member.role is None:
            return []
        return [RoleResponse.model_validate(ctx.member.role)]

    # Organization scope — return all roles
    roles = await list_roles(db, ctx.organization.id)
    return [RoleResponse.model_validate(r) for r in roles]
```

**Critical:** Self-filtering is the controller's responsibility. The service layer always returns all records for the organization.

## Service Layer

All service functions are `async` and scoped by `organizationId`.

### list_roles

```python
async def list_roles(db: AsyncSession, organization_id: str) -> list[Role]:
    """Return all roles for the given organization, ordered by createdAt."""
```

### get_role_by_id

```python
async def get_role_by_id(db: AsyncSession, organization_id: str, role_id: str) -> Role:
    """
    Fetch a role by id, scoped to the given organization.
    Raises 404 if not found.
    """
```

### create_role

```python
async def create_role(
    db: AsyncSession,
    organization_id: str,
    data: RoleCreateRequest,
) -> Role:
    """
    Insert a new Role record.
    Raises 409 if a role with the same name already exists.
    """
```

### update_role

```python
async def update_role(
    db: AsyncSession,
    organization_id: str,
    role_id: str,
    data: RoleUpdateRequest,
) -> Role:
    """
    Apply a partial update to an existing role.
    Raises 404 if not found, 409 on name conflict.
    """
```

### delete_role

```python
async def delete_role(db: AsyncSession, organization_id: str, role_id: str) -> None:
    """
    Delete a role by id, scoped to the given organization.
    Raises 404 if not found.
    """
```

## Schemas

### RoleCreateRequest

```python
class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    permissions: PermissionsDict
```

### RoleUpdateRequest

```python
class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    permissions: PermissionsDict | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "RoleUpdateRequest":
        if self.name is None and self.permissions is None:
            raise ValueError("At least one field must be provided")
        return self
```

### RoleResponse

```python
class RoleResponse(BaseModel):
    id: str
    organizationId: str
    name: str
    permissions: PermissionsDict
    createdAt: datetime
    updatedAt: datetime

    model_config = {"from_attributes": True}
```

### PermissionsDict

```python
# Type alias for the permissions JSON structure
PermissionsDict = dict[str, dict[str, str]]

# Example:
# {
#   "attendance": { "view": "organization", "create": "self" },
#   "leaves": { "view": "department", "approve": "organization" }
# }
```

## Security Rules

### 1. Always Scope by Organization

Every query MUST include `organizationId` in the WHERE clause:

```python
# ✅ Correct
result = await db.execute(
    select(Role).where(
        Role.id == role_id,
        Role.organizationId == organization_id
    )
)

# ❌ CRITICAL SECURITY VULNERABILITY
result = await db.execute(
    select(Role).where(Role.id == role_id)
)
```

### 2. Soft Deletes Only

Never hard-delete HR data. For roles, we use hard deletes because:
- Roles are configuration, not transactional data
- Members have a foreign key to roles that should cascade
- Deleted roles should not appear in any queries

However, if a role is in use (has members assigned), consider preventing deletion or implementing a soft delete pattern.

### 3. Validate Permissions JSON

The permissions JSON is free-form, but should be validated:
- Module keys should match known HRMS modules
- Action keys should be valid for the module
- Scope values should be one of: `none`, `self`, `department`, `organization`

Currently, validation is lenient to allow flexibility. Consider adding strict validation if needed.

### 4. Name Uniqueness

Role names must be unique within an organization. The database enforces this with a unique constraint:

```prisma
@@unique([organizationId, name])
```

The service layer catches `IntegrityError` and returns `409 Conflict`.

## Error Handling

### Standard Error Responses

| Status | Condition |
|--------|-----------|
| `400 Bad Request` | Invalid request body (Pydantic validation) |
| `403 Forbidden` | No permission for the action |
| `404 Not Found` | Role or organization not found |
| `409 Conflict` | Role name already exists |
| `500 Internal Server Error` | Unexpected server error |

### Error Response Format

```json
{
  "detail": "Human-readable error message"
}
```

## Testing

### Unit Tests

Test service functions in isolation:

```python
import pytest
from app.modules.role.service import create_role, list_roles
from app.modules.role.schema import RoleCreateRequest

@pytest.mark.asyncio
async def test_create_role(db_session, test_organization):
    data = RoleCreateRequest(
        name="Test Role",
        permissions={"attendance": {"view": "organization"}}
    )
    
    role = await create_role(db_session, test_organization.id, data)
    
    assert role.name == "Test Role"
    assert role.organizationId == test_organization.id
    assert role.permissions == {"attendance": {"view": "organization"}}

@pytest.mark.asyncio
async def test_list_roles_scoped_to_organization(db_session, test_organization, other_organization):
    # Create roles in both organizations
    await create_role(db_session, test_organization.id, RoleCreateRequest(name="Role 1", permissions={}))
    await create_role(db_session, other_organization.id, RoleCreateRequest(name="Role 2", permissions={}))
    
    # List should only return roles from test_organization
    roles = await list_roles(db_session, test_organization.id)
    
    assert len(roles) == 1
    assert roles[0].name == "Role 1"
```

### Integration Tests

Test the full request flow:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_role_endpoint(client: AsyncClient, test_member_with_permission):
    response = await client.post(
        "/roles",
        json={
            "name": "New Role",
            "permissions": {"attendance": {"view": "organization"}}
        },
        headers={
            "x-organization-slug": test_member_with_permission.organization.slug,
            "x-membership-id": test_member_with_permission.id,
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Role"
    assert data["permissions"]["attendance"]["view"] == "organization"

@pytest.mark.asyncio
async def test_create_role_without_permission(client: AsyncClient, test_member_without_permission):
    response = await client.post(
        "/roles",
        json={"name": "New Role", "permissions": {}},
        headers={
            "x-organization-slug": test_member_without_permission.organization.slug,
            "x-membership-id": test_member_without_permission.id,
        }
    )
    
    assert response.status_code == 403
```

## Related Files

### Backend
- `app/shared/deps/permissions.py` — Permission enforcement dependency
- `app/shared/utils/permissions.py` — Permission utility functions
- `app/shared/deps/organization_member.py` — Context resolution
- `app/models/role.py` — Prisma model

### Frontend
- `client/src/modules/roles/` — Frontend role management UI
- `client/src/lib/hrms-roles.ts` — Navigation and permission helpers

### Documentation
- `.agents/steering/instruction.md` — Complete system documentation
- `client/src/modules/roles/README.md` — Frontend module documentation
