from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.shared.config import get_settings

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS_API_URL = "https://sheets.googleapis.com/v4/spreadsheets"


@dataclass(frozen=True)
class SheetValueBlock:
    sheet_title: str
    values: list[list[str]]


@dataclass(frozen=True)
class CreatedSpreadsheet:
    spreadsheet_id: str
    spreadsheet_url: str
    sheet_id: int
    sheet_title: str


@dataclass(frozen=True)
class CreatedSheetTab:
    sheet_id: int
    sheet_title: str


@dataclass(frozen=True)
class AnalysisMergeRange:
    start_column_index: int
    end_column_index: int


def sanitize_sheet_title(value: str) -> str:
    cleaned = "".join("-" if char in "[]:*?/\\" else char for char in value).strip()
    return (cleaned or "Evaluation")[:100]


def make_unique_sheet_titles(names: list[str]) -> list[str]:
    used: set[str] = set()
    titles: list[str] = []
    for name in names:
        base = sanitize_sheet_title(name)
        title = base
        suffix = 2
        while title.lower() in used:
            suffix_text = f" {suffix}"
            title = f"{base[:100 - len(suffix_text)]}{suffix_text}"
            suffix += 1
        used.add(title.lower())
        titles.append(title)
    return titles


def _a1_sheet_name(title: str) -> str:
    escaped_title = sanitize_sheet_title(title).replace("'", "''")
    return f"'{escaped_title}'"


class GoogleSheetsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()

    async def create_evaluation_spreadsheet(
        self,
        user_id: str,
        title: str,
        first_tab_title: str,
        value_blocks: list[SheetValueBlock],
    ) -> CreatedSpreadsheet:
        access_token = await self._get_access_token(user_id)
        safe_tab_title = sanitize_sheet_title(first_tab_title)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                SHEETS_API_URL,
                headers=self._auth_headers(access_token),
                json={
                    "properties": {"title": title},
                    "sheets": [{"properties": {"title": safe_tab_title}}],
                },
            )
            if response.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=self._google_error_message(response, "Google Sheets spreadsheet creation failed"),
                )

            payload = response.json()
            spreadsheet_id = str(payload["spreadsheetId"])
            spreadsheet_url = str(payload["spreadsheetUrl"])
            sheet = payload["sheets"][0]["properties"]
            sheet_id = int(sheet["sheetId"])
            sheet_title = str(sheet["title"])

            await self._write_values(client, access_token, spreadsheet_id, value_blocks)

        return CreatedSpreadsheet(
            spreadsheet_id=spreadsheet_id,
            spreadsheet_url=spreadsheet_url,
            sheet_id=sheet_id,
            sheet_title=sheet_title,
        )

    async def create_sheet_tab(
        self,
        user_id: str,
        spreadsheet_id: str,
        title: str,
    ) -> CreatedSheetTab:
        access_token = await self._get_access_token(user_id)
        safe_title = sanitize_sheet_title(title)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{SHEETS_API_URL}/{spreadsheet_id}:batchUpdate",
                headers=self._auth_headers(access_token),
                json={
                    "requests": [
                        {
                            "addSheet": {
                                "properties": {
                                    "title": safe_title,
                                }
                            }
                        }
                    ]
                },
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Sheets tab creation failed"),
            )

        properties = response.json()["replies"][0]["addSheet"]["properties"]
        return CreatedSheetTab(
            sheet_id=int(properties["sheetId"]),
            sheet_title=str(properties["title"]),
        )

    async def rename_sheet_tab(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_id: int,
        title: str,
    ) -> str:
        access_token = await self._get_access_token(user_id)
        safe_title = sanitize_sheet_title(title)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{SHEETS_API_URL}/{spreadsheet_id}:batchUpdate",
                headers=self._auth_headers(access_token),
                json={
                    "requests": [
                        {
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": sheet_id,
                                    "title": safe_title,
                                },
                                "fields": "title",
                            }
                        }
                    ]
                },
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Sheets tab rename failed"),
            )

        return safe_title

    async def write_values(
        self,
        user_id: str,
        spreadsheet_id: str,
        value_blocks: list[SheetValueBlock],
    ) -> None:
        access_token = await self._get_access_token(user_id)
        async with httpx.AsyncClient(timeout=30) as client:
            await self._write_values(client, access_token, spreadsheet_id, value_blocks)

    async def append_values(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_title: str,
        rows: list[list[str]],
    ) -> None:
        if not rows:
            return

        access_token = await self._get_access_token(user_id)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{SHEETS_API_URL}/{spreadsheet_id}/values/{_a1_sheet_name(sheet_title)}!A:A:append",
                headers=self._auth_headers(access_token),
                params={
                    "valueInputOption": "USER_ENTERED",
                    "insertDataOption": "INSERT_ROWS",
                },
                json={"values": rows},
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Sheets row append failed"),
            )

    async def clear_values(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_title: str,
        range_name: str = "A:ZZ",
    ) -> None:
        access_token = await self._get_access_token(user_id)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{SHEETS_API_URL}/{spreadsheet_id}/values/{_a1_sheet_name(sheet_title)}!{range_name}:clear",
                headers=self._auth_headers(access_token),
                json={},
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Sheets clearing failed"),
            )

    async def get_sheet_id(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_title: str,
    ) -> int | None:
        access_token = await self._get_access_token(user_id)
        safe_title = sanitize_sheet_title(sheet_title)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{SHEETS_API_URL}/{spreadsheet_id}",
                headers=self._auth_headers(access_token),
                params={"fields": "sheets.properties"},
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Sheets metadata reading failed"),
            )

        for sheet in response.json().get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == safe_title:
                return int(properties["sheetId"])
        return None

    async def format_stage_sheet(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_id: int,
        evaluation_type: str | None,
        category_count: int,
        row_count: int,
    ) -> None:
        requests: list[dict[str, object]] = [
            self._column_width_request(sheet_id, 0, 1, 240),
            self._column_width_request(sheet_id, 1, 2, 280),
            self._clip_text_request(sheet_id),
            self._header_format_request(sheet_id, 0, max(2 + category_count + 2, 4)),
        ]
        if evaluation_type == "CHECKBOX" and category_count > 0:
            requests.append(
                {
                    "setDataValidation": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 1,
                            "endRowIndex": max(row_count, 250),
                            "startColumnIndex": 2,
                            "endColumnIndex": 2 + category_count,
                        },
                        "rule": {
                            "condition": {"type": "BOOLEAN"},
                            "strict": True,
                            "showCustomUi": True,
                        },
                    }
                }
            )
        await self._batch_update(user_id, spreadsheet_id, requests)

    async def delete_column(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_id: int,
        column_index: int,
    ) -> None:
        await self._batch_update(
            user_id,
            spreadsheet_id,
            [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "COLUMNS",
                            "startIndex": column_index,
                            "endIndex": column_index + 1,
                        }
                    }
                }
            ],
        )

    async def format_analysis_sheet(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_id: int,
        merge_ranges: list[AnalysisMergeRange],
        column_count: int,
    ) -> None:
        requests: list[dict[str, object]] = [
            self._column_width_request(sheet_id, 0, 1, 240),
            self._column_width_request(sheet_id, 1, 2, 280),
            self._clip_text_request(sheet_id),
            self._header_format_request(sheet_id, 0, max(column_count, 2)),
            self._header_format_request(sheet_id, 1, max(column_count, 2)),
            {
                "unmergeCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": max(column_count, 2),
                    }
                }
            },
        ]
        for merge_range in merge_ranges:
            if merge_range.end_column_index <= merge_range.start_column_index + 1:
                continue
            requests.append(
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": merge_range.start_column_index,
                            "endColumnIndex": merge_range.end_column_index,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                }
            )
        await self._batch_update(user_id, spreadsheet_id, requests)

    async def unmerge_header_row(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_id: int,
        column_count: int,
    ) -> None:
        await self._batch_update(
            user_id,
            spreadsheet_id,
            [
                {
                    "unmergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": max(column_count, 2),
                        }
                    }
                }
            ],
        )

    async def get_values(
        self,
        user_id: str,
        spreadsheet_id: str,
        sheet_title: str,
        range_name: str = "A:Z",
    ) -> list[list[str]]:
        access_token = await self._get_access_token(user_id)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{SHEETS_API_URL}/{spreadsheet_id}/values/{_a1_sheet_name(sheet_title)}!{range_name}",
                headers=self._auth_headers(access_token),
            )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Sheets row reading failed"),
            )

        values = response.json().get("values", [])
        return [
            [str(cell) for cell in row]
            for row in values
            if isinstance(row, list)
        ]

    async def _write_values(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        spreadsheet_id: str,
        value_blocks: list[SheetValueBlock],
    ) -> None:
        if not value_blocks:
            return

        response = await client.post(
            f"{SHEETS_API_URL}/{spreadsheet_id}/values:batchUpdate",
            headers=self._auth_headers(access_token),
            json={
                "valueInputOption": "USER_ENTERED",
                "data": [
                    {
                        "range": f"{_a1_sheet_name(block.sheet_title)}!A1",
                        "majorDimension": "ROWS",
                        "values": block.values,
                    }
                    for block in value_blocks
                ],
            },
        )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Sheets row writing failed"),
            )

    async def _batch_update(
        self,
        user_id: str,
        spreadsheet_id: str,
        requests: list[dict[str, object]],
    ) -> None:
        if not requests:
            return
        access_token = await self._get_access_token(user_id)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{SHEETS_API_URL}/{spreadsheet_id}:batchUpdate",
                headers=self._auth_headers(access_token),
                json={"requests": requests},
            )
        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=self._google_error_message(response, "Google Sheets formatting failed"),
            )

    def _column_width_request(
        self,
        sheet_id: int,
        start_index: int,
        end_index: int,
        pixel_size: int,
    ) -> dict[str, object]:
        return {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": start_index,
                    "endIndex": end_index,
                },
                "properties": {"pixelSize": pixel_size},
                "fields": "pixelSize",
            }
        }

    def _clip_text_request(self, sheet_id: int) -> dict[str, object]:
        return {
            "repeatCell": {
                "range": {"sheetId": sheet_id},
                "cell": {
                    "userEnteredFormat": {
                        "wrapStrategy": "CLIP",
                        "verticalAlignment": "MIDDLE",
                    }
                },
                "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment",
            }
        }

    def _header_format_request(
        self,
        sheet_id: int,
        row_index: int,
        column_count: int,
    ) -> dict[str, object]:
        return {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": column_count,
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "textFormat": {"bold": True},
                        "wrapStrategy": "CLIP",
                    }
                },
                "fields": (
                    "userEnteredFormat.horizontalAlignment,"
                    "userEnteredFormat.verticalAlignment,"
                    "userEnteredFormat.textFormat.bold,"
                    "userEnteredFormat.wrapStrategy"
                ),
            }
        }

    async def _get_access_token(self, user_id: str) -> str:
        account = await self._get_google_account(user_id)
        if account is None:
            raise HTTPException(
                status_code=400,
                detail="Connect a Google account before generating an evaluation workspace",
            )

        if not self._has_sheets_scope(account):
            raise HTTPException(
                status_code=400,
                detail="Reconnect Google with Sheets access before generating an evaluation workspace",
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

    def _has_sheets_scope(self, account: Account) -> bool:
        if not account.scope:
            return False
        return SHEETS_SCOPE in account.scope.replace(",", " ").split()

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
        expires_in = int(payload.get("expires_in", 3600))
        account.accessTokenExpiresAt = datetime.now(UTC) + timedelta(seconds=expires_in)
        if "scope" in payload:
            account.scope = str(payload["scope"]).replace(" ", ",")
        self.db.add(account)
        await self.db.flush()
        return access_token

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
