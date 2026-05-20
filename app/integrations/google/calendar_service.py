from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.shared.config import get_settings

CALENDAR_EVENTS_SCOPE = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
TOKEN_URL = "https://oauth2.googleapis.com/token"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


@dataclass(frozen=True)
class CreatedCalendarMeeting:
    event_id: str
    html_link: str | None
    meeting_url: str
    starts_at: datetime
    ends_at: datetime


class GoogleCalendarService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def create_meet_event(
        self,
        user_id: str,
        summary: str,
        description: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> CreatedCalendarMeeting:
        access_token = await self._get_access_token(user_id)
        start = self._normalize_datetime(starts_at)
        end = self._normalize_datetime(ends_at)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                CALENDAR_EVENTS_URL,
                headers=self._auth_headers(access_token),
                params={
                    "conferenceDataVersion": 1,
                    "sendUpdates": "none",
                },
                json={
                    "summary": summary,
                    "description": description,
                    "start": {"dateTime": start.isoformat()},
                    "end": {"dateTime": end.isoformat()},
                    "conferenceData": {
                        "createRequest": {
                            "requestId": uuid4().hex,
                            "conferenceSolutionKey": {"type": "hangoutsMeet"},
                        }
                    },
                },
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Calendar event creation failed"),
            )

        payload = response.json()
        meeting_url = self._meeting_url(payload)
        if meeting_url is None:
            raise HTTPException(status_code=502, detail="Google Calendar did not return a Meet link")

        return CreatedCalendarMeeting(
            event_id=str(payload["id"]),
            html_link=str(payload["htmlLink"]) if payload.get("htmlLink") else None,
            meeting_url=meeting_url,
            starts_at=start,
            ends_at=end,
        )

    async def update_meet_event(
        self,
        user_id: str,
        event_id: str,
        summary: str,
        description: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> CreatedCalendarMeeting:
        access_token = await self._get_access_token(user_id)
        start = self._normalize_datetime(starts_at)
        end = self._normalize_datetime(ends_at)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.patch(
                f"{CALENDAR_EVENTS_URL}/{event_id}",
                headers=self._auth_headers(access_token),
                params={
                    "sendUpdates": "none",
                },
                json={
                    "summary": summary,
                    "description": description,
                    "start": {"dateTime": start.isoformat()},
                    "end": {"dateTime": end.isoformat()},
                },
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Calendar event update failed"),
            )

        payload = response.json()
        meeting_url = self._meeting_url(payload)
        if meeting_url is None:
            raise HTTPException(status_code=502, detail="Google Calendar did not return a Meet link")

        return CreatedCalendarMeeting(
            event_id=str(payload["id"]),
            html_link=str(payload["htmlLink"]) if payload.get("htmlLink") else None,
            meeting_url=meeting_url,
            starts_at=start,
            ends_at=end,
        )

    async def _get_access_token(self, user_id: str) -> str:
        account = await self._get_google_account(user_id)
        if account is None:
            raise HTTPException(
                status_code=400,
                detail="Connect a Google account before scheduling interviews",
            )

        if not self._has_calendar_scope(account):
            raise HTTPException(
                status_code=400,
                detail="Reconnect Google with Calendar access before scheduling interviews",
            )

        if account.accessToken and not self._is_expired(account.accessTokenExpiresAt):
            return account.accessToken

        if not account.refreshToken:
            raise HTTPException(
                status_code=400,
                detail="Google refresh token is missing. Reconnect Google and try again",
            )

        return await self._refresh_access_token(account)

    async def _get_google_account(self, user_id: str) -> Account | None:
        result = await self.db.execute(
            select(Account)
            .where(
                Account.userId == user_id,
                Account.providerId == "google",
            )
            .order_by(Account.updatedAt.desc())
        )
        return result.scalars().first()

    def _has_calendar_scope(self, account: Account) -> bool:
        if not account.scope:
            return False
        scopes = set(account.scope.replace(",", " ").split())
        return CALENDAR_SCOPE in scopes or CALENDAR_EVENTS_SCOPE in scopes

    def _is_expired(self, expires_at: datetime | None) -> bool:
        if expires_at is None:
            return True
        expiry = expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return expiry <= datetime.now(UTC) + timedelta(minutes=2)

    async def _refresh_access_token(self, account: Account) -> str:
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise HTTPException(status_code=400, detail="Google OAuth credentials are not configured")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                TOKEN_URL,
                data={
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "refresh_token": account.refreshToken,
                    "grant_type": "refresh_token",
                },
            )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google token refresh failed"),
            )

        payload = response.json()
        access_token = str(payload["access_token"])
        account.accessToken = access_token
        account.accessTokenExpiresAt = datetime.now(UTC) + timedelta(seconds=int(payload.get("expires_in", 3600)))
        if "scope" in payload:
            account.scope = str(payload["scope"]).replace(" ", ",")
        self.db.add(account)
        await self.db.flush()
        return access_token

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _meeting_url(self, payload: dict) -> str | None:
        hangout_link = payload.get("hangoutLink")
        if isinstance(hangout_link, str) and hangout_link:
            return hangout_link
        entry_points = payload.get("conferenceData", {}).get("entryPoints", [])
        if isinstance(entry_points, list):
            for entry in entry_points:
                if isinstance(entry, dict) and entry.get("entryPointType") == "video":
                    uri = entry.get("uri")
                    if isinstance(uri, str) and uri:
                        return uri
        return None

    def _auth_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _google_error_message(self, response: httpx.Response, fallback: str) -> str:
        try:
            payload = response.json()
        except ValueError:
            return fallback
        message = payload.get("error", {}).get("message")
        if isinstance(message, str) and message:
            return message
        return fallback
