class MicrosoftGraphError(Exception):
    """Base exception for Microsoft Graph API errors."""


class MicrosoftGraphAuthError(MicrosoftGraphError):
    """Token expired, invalid, or missing."""


class MicrosoftGraphRateLimitError(MicrosoftGraphError):
    """429 — too many requests, retries exhausted."""


class MicrosoftGraphApiError(MicrosoftGraphError):
    """Non-429 HTTP error from Graph API."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Graph API error {status_code}: {message}")


class MicrosoftGraphConfigurationError(MicrosoftGraphError):
    """Missing or invalid integration settings."""
