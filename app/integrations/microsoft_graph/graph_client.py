import asyncio
import logging
from typing import Any

import httpx

from app.integrations.microsoft_graph.exceptions import (
    MicrosoftGraphApiError,
    MicrosoftGraphAuthError,
    MicrosoftGraphRateLimitError,
)
from app.integrations.microsoft_graph.schema import (
    ConnectionTestResult,
    MicrosoftGroup,
    MicrosoftOrganization,
    MicrosoftUser,
)
from app.integrations.microsoft_graph.token_manager import TokenManager

logger = logging.getLogger("klhrms.microsoft.graph")

GRAPH_URL = "https://graph.microsoft.com/v1.0"
MAX_RETRIES = 3
BASE_DELAY = 1.0

SELECT_USER_FIELDS = (
    "id,displayName,userPrincipalName,mail,employeeId,"
    "department,jobTitle,accountEnabled"
)


class MicrosoftGraphClient:
    """Raw Graph HTTP client with pagination, retry/backoff, and error handling."""

    def __init__(self, token_manager: TokenManager) -> None:
        self._token_manager = token_manager

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        token = await self._token_manager.get_token()
        url = path if path.startswith("http") else f"{GRAPH_URL}{path}"
        headers = {"Authorization": f"Bearer {token}", "ConsistencyLevel": "eventual"}
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.request(method, url, headers=headers, **kwargs)

                if resp.status_code == 401:
                    raise MicrosoftGraphAuthError(
                        "Token expired or invalid — re-auth required"
                    )
                if resp.status_code == 403:
                    body = resp.json()
                    error_msg = (
                        body.get("error", {}).get("message", "Insufficient permissions")
                    )
                    raise MicrosoftGraphApiError(403, error_msg)
                if resp.status_code == 429:
                    retry_after = int(
                        resp.headers.get("Retry-After", BASE_DELAY * (2**attempt))
                    )
                    logger.warning(
                        "Rate limited, retrying in %ss (attempt %d/%d)",
                        retry_after,
                        attempt + 1,
                        MAX_RETRIES,
                    )
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp.json()

            except httpx.TimeoutException:
                if attempt == MAX_RETRIES - 1:
                    raise MicrosoftGraphRateLimitError(
                        "Request timed out after max retries"
                    )
                delay = BASE_DELAY * (2**attempt)
                logger.warning(
                    "Timeout, retrying in %ss (attempt %d/%d)",
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                await asyncio.sleep(delay)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    retry_after = int(
                        e.response.headers.get("Retry-After", BASE_DELAY * (2**attempt))
                    )
                    await asyncio.sleep(retry_after)
                    continue
                raise MicrosoftGraphApiError(e.response.status_code, str(e))

        raise MicrosoftGraphRateLimitError("Max retries exceeded")

    async def get(self, path: str) -> dict[str, Any]:
        return await self._request("GET", path)

    async def get_all_pages(self, path: str) -> list[dict[str, Any]]:
        """Automatically follow @odata.nextLink until all pages consumed."""
        items: list[dict[str, Any]] = []
        next_path = path
        while next_path:
            data = await self.get(next_path)
            items.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")
            next_path = next_link.replace(GRAPH_URL, "") if next_link else None
        return items

    # ── Domain methods ────────────────────────────────────────────────────────

    async def get_organization(self) -> MicrosoftOrganization:
        data = await self.get("/organization")
        orgs = data.get("value", [])
        if orgs:
            o = orgs[0]
            return MicrosoftOrganization(
                id=o.get("id", ""),
                display_name=o.get("displayName", ""),
                tenant_branding=o.get("marketingNotificationEmails", []),
            )
        return MicrosoftOrganization()

    async def get_users(self) -> list[MicrosoftUser]:
        raw = await self.get_all_pages(f"/users?$select={SELECT_USER_FIELDS}&$top=100")
        return [
            MicrosoftUser(
                graph_id=u.get("id", ""),
                display_name=u.get("displayName", ""),
                user_principal_name=u.get("userPrincipalName"),
                email=u.get("mail"),
                employee_id=u.get("employeeId"),
                department=u.get("department"),
                job_title=u.get("jobTitle"),
                mobile_phone=u.get("mobilePhone"),
                office_location=u.get("officeLocation"),
                account_enabled=u.get("accountEnabled", True),
            )
            for u in raw
        ]

    async def get_user_manager(self, user_id: str) -> dict[str, Any] | None:
        try:
            return await self.get(f"/users/{user_id}/manager")
        except MicrosoftGraphApiError as e:
            if e.status_code == 404:
                return None
            raise

    async def get_user_photo_bytes(self, user_id: str) -> bytes | None:
        try:
            token = await self._token_manager.get_token()
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{GRAPH_URL}/users/{user_id}/photo/$value",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.content
        except Exception:
            return None

    async def get_user_group_ids(self, user_id: str) -> list[str]:
        try:
            data = await self.get_all_pages(
                f"/users/{user_id}/memberOf/microsoft.graph.group"
            )
            return [g.get("id", "") for g in data if g.get("id")]
        except MicrosoftGraphApiError:
            return []

    async def get_groups(self) -> list[MicrosoftGroup]:
        raw = await self.get_all_pages(
            "/groups?$select=id,displayName,description,groupTypes&$top=100"
        )
        return [
            MicrosoftGroup(
                graph_id=g.get("id", ""),
                display_name=g.get("displayName", ""),
                description=g.get("description"),
                group_type="security" if "SecurityEnabled" in g.get("groupTypes", []) else "mail",
            )
            for g in raw
        ]

    async def test_connection(self) -> ConnectionTestResult:
        try:
            org = await self.get_organization()
            return ConnectionTestResult(
                connected=True,
                tenant_name=org.display_name,
                tenant_id=org.id,
            )
        except MicrosoftGraphAuthError as e:
            return ConnectionTestResult(connected=False, error=str(e))
        except MicrosoftGraphApiError as e:
            return ConnectionTestResult(connected=False, error=str(e))
        except Exception as e:
            return ConnectionTestResult(connected=False, error=str(e))
