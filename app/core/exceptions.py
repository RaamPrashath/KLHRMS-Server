"""
Domain exception hierarchy for KL HRMS.
All custom exceptions raised in services/repositories map to HTTP responses
via the exception handlers registered in main.py.
"""
from fastapi import HTTPException, status


class HRMSException(Exception):
    """Base class for all KL HRMS domain exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


# ── 400 Bad Request ──────────────────────────────────────────────────────────

class ValidationError(HRMSException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Validation error."


# ── 401 Unauthorized ─────────────────────────────────────────────────────────

class AuthenticationError(HRMSException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Authentication required."


class InvalidTokenError(AuthenticationError):
    detail = "Token is invalid or expired."


# ── 403 Forbidden ────────────────────────────────────────────────────────────

class PermissionDeniedError(HRMSException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "You do not have permission to perform this action."


# ── 404 Not Found ────────────────────────────────────────────────────────────

class NotFoundError(HRMSException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found."


# ── 409 Conflict ─────────────────────────────────────────────────────────────

class ConflictError(HRMSException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource already exists."


# ── 422 Unprocessable ────────────────────────────────────────────────────────

class BusinessRuleError(HRMSException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Business rule violation."


# ── Tenant ───────────────────────────────────────────────────────────────────

class TenantNotFoundError(NotFoundError):
    detail = "Organization not found or inactive."


class TenantMismatchError(PermissionDeniedError):
    detail = "Resource does not belong to your organization."


# ── HTTP helper ──────────────────────────────────────────────────────────────

def raise_http(exc: HRMSException) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)
