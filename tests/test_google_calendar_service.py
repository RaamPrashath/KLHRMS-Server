from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.integrations.google import calendar_service
from app.integrations.google.calendar_service import GoogleCalendarService
from app.models.account import Account


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeAsyncClient:
    captured_post: dict[str, Any] | None = None
    response = FakeResponse(
        200,
        {
            "id": "event-1",
            "htmlLink": "https://calendar.google.com/event?eid=event-1",
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
        },
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> FakeAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        FakeAsyncClient.captured_post = {"url": url, **kwargs}
        return FakeAsyncClient.response


class FakeDb:
    def add(self, item: Any) -> None:
        pass

    async def flush(self) -> None:
        pass


def _service() -> GoogleCalendarService:
    service = GoogleCalendarService.__new__(GoogleCalendarService)
    service.db = None
    return service


@pytest.mark.asyncio
async def test_create_meet_event_requests_google_meet_conference_data(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_get_access_token(self: GoogleCalendarService, user_id: str) -> str:
        assert user_id == "user-1"
        return "access-token"

    monkeypatch.setattr(GoogleCalendarService, "_get_access_token", fake_get_access_token)
    monkeypatch.setattr(calendar_service.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.response = FakeResponse(
        200,
        {
            "id": "event-1",
            "htmlLink": "https://calendar.google.com/event?eid=event-1",
            "hangoutLink": "https://meet.google.com/abc-defg-hij",
        },
    )

    meeting = await _service().create_meet_event(
        user_id="user-1",
        summary="Interview",
        description="Candidate interview",
        starts_at=datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
        ends_at=datetime(2026, 6, 9, 10, 30, tzinfo=UTC),
    )

    captured = FakeAsyncClient.captured_post
    assert captured is not None
    assert captured["url"] == calendar_service.CALENDAR_EVENTS_URL
    assert captured["headers"]["Authorization"] == "Bearer access-token"
    assert captured["params"] == {"conferenceDataVersion": 1, "sendUpdates": "none"}
    assert captured["json"]["conferenceData"]["createRequest"]["conferenceSolutionKey"] == {
        "type": "hangoutsMeet",
    }
    assert meeting.event_id == "event-1"
    assert meeting.meeting_url == "https://meet.google.com/abc-defg-hij"


@pytest.mark.asyncio
async def test_create_meet_event_fails_when_google_does_not_return_meet_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_access_token(self: GoogleCalendarService, user_id: str) -> str:
        return "access-token"

    monkeypatch.setattr(GoogleCalendarService, "_get_access_token", fake_get_access_token)
    monkeypatch.setattr(calendar_service.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.response = FakeResponse(
        200,
        {
            "id": "event-1",
            "htmlLink": "https://calendar.google.com/event?eid=event-1",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        await _service().create_meet_event(
            user_id="user-1",
            summary="Interview",
            description="Candidate interview",
            starts_at=datetime(2026, 6, 9, 10, 0, tzinfo=UTC),
            ends_at=datetime(2026, 6, 9, 10, 30, tzinfo=UTC),
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Google Calendar did not return a Meet link"


def test_calendar_scope_accepts_full_calendar_or_events_scope() -> None:
    service = _service()

    assert service._has_calendar_scope(Account(scope=calendar_service.CALENDAR_SCOPE))
    assert service._has_calendar_scope(Account(scope=calendar_service.CALENDAR_EVENTS_SCOPE))
    assert not service._has_calendar_scope(Account(scope="openid,email,profile"))


@pytest.mark.asyncio
async def test_refresh_access_token_invalid_grant_asks_user_to_reconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GoogleCalendarService.__new__(GoogleCalendarService)
    service.db = FakeDb()
    service.settings = SimpleNamespace(
        google_client_id="client-id",
        google_client_secret="client-secret",
    )
    monkeypatch.setattr(calendar_service.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.response = FakeResponse(
        400,
        {
            "error": "invalid_grant",
            "error_description": "Token has been expired or revoked.",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        await service._refresh_access_token(Account(refreshToken="refresh-token"))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == calendar_service.GOOGLE_RECONNECT_REQUIRED_MESSAGE
