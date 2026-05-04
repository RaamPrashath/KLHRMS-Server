"""
Domain exception hierarchy for KL HRMS.

Raise these from services and repositories — never raise HTTPException there.
The exception handler in main.py maps them to HTTP responses automatically.
"""
from fastapi import status


class HRMSException(Exception):
    """Base class for all KL HRMS domain exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


# ── 400 ──────────────────────────────────────────────────────────────────────
class ValidationError(HRMSException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Validation error."


# ── 401 ──────────────────────────────────────────────────────────────────────
class AuthenticationError(HRMSException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authentication required."


class InvalidTokenError(AuthenticationError):
    detail = "Token is invalid or expired."


# ── 403 ──────────────────────────────────────────────────────────────────────
class PermissionDeniedError(HRMSException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You do not have permission to perform this action."


# ── 404 ──────────────────────────────────────────────────────────────────────
class NotFoundError(HRMSException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found."


# ── 409 ──────────────────────────────────────────────────────────────────────
class ConflictError(HRMSException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource already exists."


# ── 422 ──────────────────────────────────────────────────────────────────────
class BusinessRuleError(HRMSException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Business rule violation."


# ── Tenant ───────────────────────────────────────────────────────────────────
class TenantNotFoundError(NotFoundError):
    detail = "Organization not found or inactive."


class TenantMismatchError(PermissionDeniedError):
    detail = "Resource does not belong to your organization."
