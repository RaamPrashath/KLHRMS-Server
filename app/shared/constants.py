"""Application-wide constants — no magic strings in the codebase."""

# ── Pagination ────────────────────────────────────────────────────────────────
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 200

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

# ── Header names ──────────────────────────────────────────────────────────────
HEADER_REQUEST_ID: str = "x-request-id"
HEADER_TENANT_ID: str = "x-organization-id"
HEADER_PROCESS_TIME: str = "x-process-time-ms"

# ── Audit log actions ─────────────────────────────────────────────────────────
AUDIT_CREATE: str = "CREATE"
AUDIT_UPDATE: str = "UPDATE"
AUDIT_DELETE: str = "DELETE"
