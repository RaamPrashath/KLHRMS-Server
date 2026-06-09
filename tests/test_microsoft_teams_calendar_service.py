from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.integrations.microsoft_graph import calendar_service as teams_calendar
from app.integrations.microsoft_graph.calendar_service import MicrosoftTeamsCalendarService


class FakeResponse:
    status_code = 201

    def json(self) -> dict:
        return {
            "id": "event-1",
            "webLink": "https://outlook.office.com/calendar/item/event-1",
            "onlineMeeting": {"joinUrl": "https://teams.microsoft.com/l/meetup-join/event-1"},
        }


class CalendarOnlyResponse:
    status_code = 201

    def json(self) -> dict:
        return {
            "id": "event-calendar-only",
            "webLink": "https://outlook.live.com/calendar/item/event-calendar-only",
            "isOnlineMeeting": False,
            "onlineMeeting": None,
        }


class RecordingAsyncClient:
    calls: list[dict] = []

    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self) -> RecordingAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return FakeResponse()

    async def patch(self, *args, **kwargs) -> None:  # pragma: no cover - forbidden guard
        raise AssertionError("Microsoft calendar service must not PATCH calendar events")

    async def delete(self, *args, **kwargs) -> None:  # pragma: no cover - forbidden guard
        raise AssertionError("Microsoft calendar service must not DELETE calendar events")


class UnauthorizedResponse:
    status_code = 401
    text = "Unauthorized"

    def json(self) -> dict:
        return {
            "error": {
                "code": "InvalidAuthenticationToken",
                "message": "Access token validation failure.",
            }
        }


class EmptyUnauthorizedResponse:
    status_code = 401
    text = ""

    def json(self) -> dict:
        raise ValueError("No JSON body")


class RetryingAsyncClient(RecordingAsyncClient):
    async def post(self, url: str, **kwargs) -> FakeResponse | UnauthorizedResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        if len(self.calls) == 1:
            return UnauthorizedResponse()
        return FakeResponse()


class CalendarOnlyAsyncClient(RecordingAsyncClient):
    async def post(self, url: str, **kwargs) -> CalendarOnlyResponse:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return CalendarOnlyResponse()


def _service() -> MicrosoftTeamsCalendarService:
    service = MicrosoftTeamsCalendarService.__new__(MicrosoftTeamsCalendarService)
    service.db = SimpleNamespace()
    service.settings = SimpleNamespace(
        microsoft_client_id="client",
        microsoft_client_secret="secret",
        microsoft_tenant_id="common",
        azure_client_id="",
        azure_client_secret="",
        azure_tenant_id="",
    )
    service._get_access_token = AsyncMock(return_value="delegated-token")
    return service


@pytest.mark.asyncio
async def test_create_teams_event_posts_without_attendees_or_invitations(monkeypatch: pytest.MonkeyPatch) -> None:
    RecordingAsyncClient.calls = []
    monkeypatch.setattr(teams_calendar.httpx, "AsyncClient", RecordingAsyncClient)
    starts_at = datetime(2026, 6, 8, 9, 0, tzinfo=UTC)

    meeting = await _service().create_teams_event(
        user_id="user-1",
        summary="Technical interview",
        description="Candidate: Ada",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=30),
    )

    assert meeting.join_url == "https://teams.microsoft.com/l/meetup-join/event-1"
    assert meeting.event_id == "event-1"
    assert RecordingAsyncClient.calls == [
        {
            "method": "POST",
            "url": teams_calendar.GRAPH_EVENTS_URL,
            "headers": {
                "Authorization": "Bearer delegated-token",
                "Content-Type": "application/json",
            },
            "json": {
                "subject": "Technical interview",
                "body": {"contentType": "text", "content": "Candidate: Ada"},
                "start": {"dateTime": "2026-06-08T09:00:00", "timeZone": "UTC"},
                "end": {"dateTime": "2026-06-08T09:30:00", "timeZone": "UTC"},
                "isOnlineMeeting": True,
                "onlineMeetingProvider": "teamsForBusiness",
            },
        }
    ]
    assert "attendees" not in RecordingAsyncClient.calls[0]["json"]


@pytest.mark.asyncio
async def test_create_teams_event_fails_when_join_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    CalendarOnlyAsyncClient.calls = []
    monkeypatch.setattr(teams_calendar.httpx, "AsyncClient", CalendarOnlyAsyncClient)
    starts_at = datetime(2026, 6, 8, 9, 0, tzinfo=UTC)

    with pytest.raises(HTTPException) as exc_info:
        await _service().create_teams_event(
            user_id="user-1",
            summary="Technical interview",
            description="Candidate: Ada",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
        )

    assert exc_info.value.status_code == 502
    assert "did not return a Teams join URL" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_create_teams_event_refreshes_and_retries_once_after_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    RetryingAsyncClient.calls = []
    monkeypatch.setattr(teams_calendar.httpx, "AsyncClient", RetryingAsyncClient)
    service = _service()
    account = SimpleNamespace(refreshToken="refresh-token")
    service._get_microsoft_account = AsyncMock(return_value=account)
    service._refresh_access_token = AsyncMock(return_value="fresh-delegated-token")

    meeting = await service.create_teams_event(
        user_id="user-1",
        summary="Technical interview",
        description="Candidate: Ada",
        starts_at=datetime(2026, 6, 8, 9, 0, tzinfo=UTC),
        ends_at=datetime(2026, 6, 8, 9, 30, tzinfo=UTC),
    )

    assert meeting.join_url == "https://teams.microsoft.com/l/meetup-join/event-1"
    assert len(RetryingAsyncClient.calls) == 2
    assert RetryingAsyncClient.calls[0]["headers"]["Authorization"] == "Bearer delegated-token"
    assert RetryingAsyncClient.calls[1]["headers"]["Authorization"] == "Bearer fresh-delegated-token"


def test_empty_calendar_unauthorized_error_mentions_mailbox_license() -> None:
    message = _service()._graph_error_message(
        EmptyUnauthorizedResponse(),  # type: ignore[arg-type]
        "Microsoft Teams calendar event creation failed",
    )

    assert "Exchange Online mailbox" in message
    assert "reconnect Microsoft" in message


@pytest.mark.asyncio
async def test_missing_linked_microsoft_account_fails_before_graph_request(monkeypatch: pytest.MonkeyPatch) -> None:
    RecordingAsyncClient.calls = []
    monkeypatch.setattr(teams_calendar.httpx, "AsyncClient", RecordingAsyncClient)
    service = _service()
    service._get_access_token = AsyncMock(
        side_effect=HTTPException(
            status_code=400,
            detail="Connect a Microsoft account before scheduling Teams interviews",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.create_teams_event(
            user_id="user-1",
            summary="Technical interview",
            description="Candidate: Ada",
            starts_at=datetime(2026, 6, 8, 9, 0, tzinfo=UTC),
            ends_at=datetime(2026, 6, 8, 9, 30, tzinfo=UTC),
        )

    assert exc_info.value.status_code == 400
    assert "Microsoft account" in str(exc_info.value.detail)
    assert RecordingAsyncClient.calls == []


def test_calendar_integration_exposes_no_calendar_modification_surface() -> None:
    service_path = Path(teams_calendar.__file__)
    source = service_path.read_text(encoding="utf-8")

    forbidden = [
        ".patch(",
        ".delete(",
        ".put(",
        "cancel",
        "sendUpdates",
        "attendees",
    ]
    for token in forbidden:
        assert token not in source

    assert not hasattr(MicrosoftTeamsCalendarService, "update_teams_event")
    assert not hasattr(MicrosoftTeamsCalendarService, "delete_teams_event")
    assert not hasattr(MicrosoftTeamsCalendarService, "cancel_teams_event")


def test_recruitment_scheduling_uses_teams_add_only_integration() -> None:
    source = Path("app/modules/candidates/service.py").read_text(encoding="utf-8")

    assert "MicrosoftTeamsCalendarService" in source
    assert "GoogleCalendarService" not in source
    assert "update_meet_event" not in source
    assert "create_meet_event" not in source
    assert "update_teams_event" not in source
    assert "delete_teams_event" not in source
    assert "cancel_teams_event" not in source
