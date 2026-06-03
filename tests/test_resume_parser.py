from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.resume_parser import service, storage
from app.modules.resume_parser.schema import ResumeParserProcessResponse
from app.modules.resume_parser.storage import resume_parser_storage_path, safe_resume_file_stem


class FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False

    def add(self, item: object) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        self.committed = True


class FakeHistoryResult:
    def all(self) -> list[object]:
        return []


class FakeHistoryDb:
    def __init__(self) -> None:
        self.query: object | None = None

    async def execute(self, query: object) -> FakeHistoryResult:
        self.query = query
        return FakeHistoryResult()


def test_resume_parser_storage_path_is_org_scoped() -> None:
    assert safe_resume_file_stem('Asha / Menon: Resume?.pdf') == "Asha Menon Resume"
    assert resume_parser_storage_path(
        organization_id="org-1",
        run_id="run-1",
        file_name="Asha Menon.json",
    ) == "org-1/resume-parser/run-1/Asha Menon.json"


@pytest.mark.asyncio
async def test_resume_parser_bucket_is_created_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class FakeResponse:
        def __init__(self, status_code: int) -> None:
            self.status_code = status_code

        def json(self) -> dict:
            return {"message": "ok"}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
            calls.append(("get", url))
            return FakeResponse(404)

        async def post(
            self,
            url: str,
            headers: dict[str, str],
            json: dict[str, object],
        ) -> FakeResponse:
            calls.append(("post", f"{url}:{json['id']}:{json['public']}"))
            return FakeResponse(201)

    monkeypatch.setattr(storage.httpx, "AsyncClient", FakeClient)

    await storage._ensure_resume_parser_bucket(
        supabase_url="https://supabase.example",
        service_role_key="service-role",
        bucket="resume-parser",
    )

    assert calls == [
        ("get", "https://supabase.example/storage/v1/bucket/resume-parser"),
        ("post", "https://supabase.example/storage/v1/bucket:resume-parser:True"),
    ]


@pytest.mark.asyncio
async def test_resume_parser_bucket_is_created_when_supabase_returns_400_bucket_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class FakeResponse:
        def __init__(self, status_code: int, message: str = "ok") -> None:
            self.status_code = status_code
            self.message = message

        def json(self) -> dict:
            return {"message": self.message}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def get(self, url: str, headers: dict[str, str]) -> FakeResponse:
            calls.append("get")
            return FakeResponse(400, "Bucket not found")

        async def post(
            self,
            url: str,
            headers: dict[str, str],
            json: dict[str, object],
        ) -> FakeResponse:
            calls.append(str(json["id"]))
            return FakeResponse(201)

    monkeypatch.setattr(storage.httpx, "AsyncClient", FakeClient)

    await storage._ensure_resume_parser_bucket(
        supabase_url="https://supabase.example",
        service_role_key="service-role",
        bucket="resume-parser",
    )

    assert calls == ["get", "resume-parser"]


@pytest.mark.asyncio
async def test_process_resume_uploads_json_and_docx(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    @dataclass(frozen=True)
    class FakeUpload:
        public_url: str

    class FakeFile:
        filename = "resume.pdf"
        content_type = "application/pdf"

        async def read(self, size: int = -1) -> bytes:
            return b"%PDF-1.4 resume"

    class FakeExtraction:
        sanitized_text = "Asha Menon Python developer"

    def fake_detect(filename: str, content_type: str | None, content: bytes) -> str:
        return "pdf"

    def fake_extract(content: bytes, file_type: str) -> FakeExtraction:
        return FakeExtraction()

    async def fake_parse(text: str) -> dict:
        return {
            "personal_info": {"name": "Asha Menon"},
            "summary": ["Python developer"],
            "experience": [],
            "education": [],
            "skills": ["Python"],
            "awards": [],
            "projects": [],
            "additional_info": {},
        }

    def fake_docx(data: dict, template_type: str) -> bytes:
        return b"docx"

    async def fake_upload(*, content: bytes, storage_path: str, content_type: str) -> FakeUpload:
        calls.append((storage_path, content_type))
        return FakeUpload(public_url=f"https://storage.example/{storage_path}")

    monkeypatch.setattr(service, "detect_resume_file_type", fake_detect)
    monkeypatch.setattr(service, "extract_resume_text", fake_extract)
    monkeypatch.setattr(service, "parse_resume_to_generation_json", fake_parse)
    monkeypatch.setattr(service, "create_resume_docx", fake_docx)
    monkeypatch.setattr(service, "upload_resume_parser_artifact", fake_upload)

    db = FakeDb()
    response = await service.process_resume_files(
        db=db,  # type: ignore[arg-type]
        organization_id="org-1",
        member_id="member-1",
        files=[FakeFile()],
        template_type="default",
    )

    assert isinstance(response, ResumeParserProcessResponse)
    assert response.processedFiles[0].status == "success"
    assert response.processedFiles[0].jsonUrl is not None
    assert response.processedFiles[0].docxUrl is not None
    assert calls[0][0].endswith("/resume.json")
    assert calls[0][1] == "application/json"
    assert calls[1][0].endswith("/resume.docx")
    assert "wordprocessingml.document" in calls[1][1]
    assert db.committed is True
    assert len(db.added) == 1
    history = db.added[0]
    assert history.memberId == "member-1"
    assert history.status == "success"


@pytest.mark.asyncio
async def test_process_resume_marks_unsupported_file_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeFile:
        filename = "resume.txt"
        content_type = "text/plain"

        async def read(self, size: int = -1) -> bytes:
            return b"hello"

    monkeypatch.setattr(service, "detect_resume_file_type", lambda *_args: "unsupported")

    db = FakeDb()
    response = await service.process_resume_files(
        db=db,  # type: ignore[arg-type]
        organization_id="org-1",
        member_id="member-1",
        files=[FakeFile()],
        template_type="default",
    )

    assert response.processedFiles[0].status == "failed"
    assert "Only PDF, DOCX, and DOC resumes are supported" in response.processedFiles[0].messages[0]
    assert db.committed is True
    assert len(db.added) == 1
    assert db.added[0].status == "failed"


@pytest.mark.asyncio
async def test_history_self_scope_filters_to_current_member() -> None:
    db = FakeHistoryDb()

    response = await service.list_resume_parser_history(
        db=db,  # type: ignore[arg-type]
        organization_id="org-1",
        member_id="member-1",
        scope="self",
    )

    assert response.scope == "self"
    assert db.query is not None
    assert '"memberId" = :memberId_1' in str(db.query)


@pytest.mark.asyncio
async def test_history_organization_scope_lists_all_org_rows() -> None:
    db = FakeHistoryDb()

    response = await service.list_resume_parser_history(
        db=db,  # type: ignore[arg-type]
        organization_id="org-1",
        member_id="member-1",
        scope="organization",
    )

    assert response.scope == "organization"
    assert db.query is not None
    assert '"organizationId" = :organizationId_1' in str(db.query)
    assert '"memberId" = :memberId_1' not in str(db.query)
