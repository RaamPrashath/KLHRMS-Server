"""
Application-wide constants for KL HRMS.
No magic strings scattered across the codebase.
"""

# ── Pagination ────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 200

# ── Redis key prefixes ────────────────────────────────────────────────────────
# Redis removed - key prefixes not used

# ── HRMS roles ────────────────────────────────────────────────────────────────
ROLE_SUPER_ADMIN: str = "super_admin"
ROLE_HR: str = "hr"
ROLE_ADMIN: str = "admin"
ROLE_MANAGER: str = "manager"
ROLE_EMPLOYEE: str = "employee"

ALL_ROLES: list[str] = [
    ROLE_SUPER_ADMIN,
    ROLE_HR,
    ROLE_ADMIN,
    ROLE_MANAGER,
    ROLE_EMPLOYEE,
]

# ── Soft-delete sentinel ──────────────────────────────────────────────────────
SOFT_DELETE_FIELD: str = "deleted_at"

# ── Audit log actions ─────────────────────────────────────────────────────────
AUDIT_CREATE: str = "CREATE"
AUDIT_UPDATE: str = "UPDATE"
AUDIT_DELETE: str = "DELETE"
AUDIT_RESTORE: str = "RESTORE"
AUDIT_LOGIN: str = "LOGIN"
AUDIT_EXPORT: str = "EXPORT"

# ── Header names ──────────────────────────────────────────────────────────────
HEADER_REQUEST_ID: str = "x-request-id"
HEADER_TENANT_ID: str = "x-organization-id"
HEADER_PROCESS_TIME: str = "x-process-time-ms"
