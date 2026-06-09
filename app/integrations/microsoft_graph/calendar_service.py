from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.shared.config import get_settings

GRAPH_EVENTS_URL = "https://graph.microsoft.com/v1.0/me/events"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
CALENDARS_READ_WRITE_SCOPE = "Calendars.ReadWrite"
MICROSOFT_REFRESH_SCOPES = "offline_access User.Read Calendars.ReadWrite"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreatedTeamsCalendarMeeting:
    event_id: str
    event_url: str | None
    join_url: str
    starts_at: datetime
    ends_at: datetime
    provider: str = "microsoft"


class MicrosoftTeamsCalendarService:
    """Delegated, add-only Microsoft calendar integration for Teams interviews.

    This service intentionally exposes only creation. Recruitment scheduling must
    never modifies existing provider calendar entries or sends provider invitations.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def create_teams_event(
        self,
        user_id: str,
        summary: str,
        description: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> CreatedTeamsCalendarMeeting:
        access_token = await self._get_access_token(user_id)
        start = self._normalize_datetime(starts_at)
        end = self._normalize_datetime(ends_at)

        payload = {
            "subject": summary,
            "body": {
                "contentType": "text",
                "content": description,
            },
            "start": {
                "dateTime": self._graph_datetime(start),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": self._graph_datetime(end),
                "timeZone": "UTC",
            },
            "isOnlineMeeting": True,
            "onlineMeetingProvider": "teamsForBusiness",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await self._post_graph_event(client, access_token, payload)

            if response.status_code == 401:
                account = await self._get_microsoft_account(user_id)
                if account is not None and account.refreshToken:
                    logger.info("Microsoft Graph calendar token was rejected; refreshing and retrying once")
                    access_token = await self._refresh_access_token(account)
                    response = await self._post_graph_event(client, access_token, payload)

        if response.status_code >= 400:
            logger.warning(
                "Microsoft Graph calendar event creation failed: status=%s detail=%s",
                response.status_code,
                self._graph_error_message(response, "Microsoft Teams calendar event creation failed"),
            )
            raise HTTPException(
                status_code=502,
                detail=self._graph_error_message(response, "Microsoft Teams calendar event creation failed"),
            )

        data = response.json()
        event_url = str(data["webLink"]) if data.get("webLink") else None
        join_url = self._join_url(data)
        if join_url is None:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Microsoft Graph created the calendar event but did not return a Teams join URL. "
                    "Use a Microsoft 365 work/school account with Teams online meetings enabled."
                ),
            )

        return CreatedTeamsCalendarMeeting(
            event_id=str(data["id"]),
            event_url=event_url,
            join_url=join_url,
            starts_at=start,
            ends_at=end,
        )

    async def _post_graph_event(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        return await client.post(
            GRAPH_EVENTS_URL,
            headers=self._auth_headers(access_token),
            json=payload,
        )

    async def _get_access_token(self, user_id: str) -> str:
        account = await self._get_microsoft_account(user_id)
        if account is None:
            raise HTTPException(
                status_code=400,
                detail="Connect a Microsoft account before scheduling Teams interviews",
            )

        if not self._has_calendar_scope(account):
            raise HTTPException(
                status_code=400,
                detail="Reconnect Microsoft with Calendar access before scheduling Teams interviews",
            )

        if account.accessToken and not self._is_expired(account.accessTokenExpiresAt):
            return account.accessToken

        if not account.refreshToken:
            raise HTTPException(
                status_code=400,
                detail="Microsoft refresh token is missing. Reconnect Microsoft and try again",
            )

        return await self._refresh_access_token(account)

    async def _get_microsoft_account(self, user_id: str) -> Account | None:
        result = await self.db.execute(
            select(Account)
            .where(
                Account.userId == user_id,
                Account.providerId == "microsoft",
            )
            .order_by(Account.updatedAt.desc())
        )
        return result.scalars().first()

    def _has_calendar_scope(self, account: Account) -> bool:
        if not account.scope:
            return False
        scopes = set(account.scope.replace(",", " ").split())
        return CALENDARS_READ_WRITE_SCOPE in scopes or f"https://graph.microsoft.com/{CALENDARS_READ_WRITE_SCOPE}" in scopes

    def _is_expired(self, expires_at: datetime | None) -> bool:
        if expires_at is None:
            return True
        expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        return expiry <= datetime.now(UTC) + timedelta(minutes=2)

    async def _refresh_access_token(self, account: Account) -> str:
        client_id = self.settings.microsoft_client_id or self.settings.azure_client_id
        client_secret = self.settings.microsoft_client_secret or self.settings.azure_client_secret
        tenant = "common"
        # Multitenant / tenant-locked mode:
        # When asked to switch back to Entra-only multitenant auth, use the
        # configured tenant/organizations authority instead of `common`:
        # tenant = self.settings.microsoft_tenant_id or self.settings.azure_tenant_id or "organizations"
        if not client_id or not client_secret:
            raise HTTPException(status_code=400, detail="Microsoft OAuth credentials are not configured")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                MICROSOFT_TOKEN_URL.format(tenant=tenant),
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": account.refreshToken,
                    "grant_type": "refresh_token",
                    "scope": MICROSOFT_REFRESH_SCOPES,
                },
            )

        if response.status_code >= 400:
            logger.warning(
                "Microsoft OAuth token refresh failed: status=%s detail=%s",
                response.status_code,
                self._graph_error_message(response, "Microsoft token refresh failed"),
            )
            raise HTTPException(
                status_code=502,
                detail=self._graph_error_message(response, "Microsoft token refresh failed"),
            )

        data = response.json()
        access_token = str(data["access_token"])
        account.accessToken = access_token
        account.accessTokenExpiresAt = datetime.now(UTC) + timedelta(seconds=int(data.get("expires_in", 3600)))
        if data.get("refresh_token"):
            account.refreshToken = str(data["refresh_token"])
        if data.get("scope"):
            account.scope = str(data["scope"]).replace(" ", ",")
        self.db.add(account)
        await self.db.flush()
        return access_token

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _graph_datetime(self, value: datetime) -> str:
        normalized = self._normalize_datetime(value)
        return normalized.replace(tzinfo=None).isoformat(timespec="seconds")

    def _join_url(self, data: dict[str, Any]) -> str | None:
        online_meeting = data.get("onlineMeeting")
        if isinstance(online_meeting, dict):
            join_url = online_meeting.get("joinUrl")
            if isinstance(join_url, str) and join_url:
                return join_url
        return None

    def _auth_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _graph_error_message(self, response: httpx.Response, fallback: str) -> str:
        try:
            payload = response.json()
        except ValueError:
            body = response.text.strip()
            if body:
                return f"{fallback}: {body[:500]}"
            if response.status_code == 401:
                return (
                    "Microsoft Calendar rejected the token. Confirm the interviewer account has an "
                    "Exchange Online mailbox/calendar license, then reconnect Microsoft in KL HRMS."
                )
            return fallback
        error = payload.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message")
            if isinstance(message, str) and message:
                if isinstance(code, str) and code:
                    return f"{code}: {message}"
                return message
        return fallback
