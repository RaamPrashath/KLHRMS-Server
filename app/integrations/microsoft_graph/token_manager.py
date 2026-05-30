import logging

import httpx
from datetime import datetime, timedelta, timezone

from app.integrations.microsoft_graph.exceptions import MicrosoftGraphAuthError

logger = logging.getLogger("klhrms.microsoft.graph")

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


class TokenManager:
    """OAuth2 client credentials token acquisition with in-memory caching."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._expires_at: datetime | None = None

    async def get_token(self) -> str:
        if (
            self._token
            and self._expires_at
            and datetime.now(timezone.utc) < self._expires_at
        ):
            return self._token
        return await self._fetch_token()

    async def _fetch_token(self) -> str:
        logger.info("Acquiring new Microsoft Graph access token")
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.post(
                    TOKEN_URL.format(tenant=self._tenant_id),
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "scope": "https://graph.microsoft.com/.default",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                self._token = data["access_token"]
                expires_in = int(data.get("expires_in", 3600))
                self._expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in - 60
                )
                logger.info("Token acquired, expires at %s", self._expires_at)
                return self._token
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Token acquisition failed: %s %s", e.response.status_code, e.response.text
                )
                raise MicrosoftGraphAuthError(
                    f"Failed to acquire token: {e.response.status_code} — {e.response.text[:200]}"
                ) from e
            except httpx.RequestError as e:
                logger.error("Token acquisition network error: %s", e)
                raise MicrosoftGraphAuthError(f"Network error acquiring token: {e}") from e
