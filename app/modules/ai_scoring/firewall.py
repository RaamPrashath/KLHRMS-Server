from __future__ import annotations

import io
from typing import Any

from app.modules.ai_scoring.schema import TextExtractionResult


def _is_near_white(color: object) -> bool:
    if color is None:
        return False
    if isinstance(color, int | float):
        return float(color) >= 0.95
    if not isinstance(color, list | tuple) or not color:
        return False
    try:
        channels = [float(channel) for channel in color]
    except (TypeError, ValueError):
        return False
    if any(channel > 1 for channel in channels):
        channels = [channel / 255 for channel in channels]
    if len(channels) == 4:
        c, m, y, k = channels[:4]
        return c <= 0.05 and m <= 0.05 and y <= 0.05 and k <= 0.05
    return all(channel >= 0.95 for channel in channels[:3])


def _flag_for_char(char: dict[str, Any]) -> str | None:
    text = str(char.get("text") or "")
    if not text.strip():
        return None
    size = char.get("size")
    try:
        if size is not None and float(size) < 4.0:
            return "micro_font"
    except (TypeError, ValueError):
        pass
    if _is_near_white(char.get("non_stroking_color")):
        return "white_text"
    return None


def _compact_snippets(chars: list[dict[str, Any]], flag_type: str, page_number: int) -> list[dict]:
    snippets: list[dict] = []
    current: list[str] = []
    for char in chars:
        if _flag_for_char(char) == flag_type:
            current.append(str(char.get("text") or ""))
            continue
        if current:
            snippet = "".join(current).strip()
            if snippet:
                snippets.append(
                    {
                        "type": flag_type,
                        "page": page_number,
                        "text": snippet[:240],
                    }
                )
            current = []
    if current:
        snippet = "".join(current).strip()
        if snippet:
            snippets.append(
                {
                    "type": flag_type,
                    "page": page_number,
                    "text": snippet[:240],
                }
            )
    return snippets


def extract_pdf_text_with_firewall(content: bytes) -> TextExtractionResult:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required to analyze PDF resumes") from exc

    extracted_pages: list[str] = []
    sanitized_pages: list[str] = []
    flags: list[dict] = []
    removed: list[dict] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            chars = sorted(page.chars or [], key=lambda item: (item.get("doctop", 0), item.get("x0", 0)))
            page_text: list[str] = []
            clean_text: list[str] = []
            page_flag_counts: dict[str, int] = {}

            for char in chars:
                text = str(char.get("text") or "")
                flag_type = _flag_for_char(char)
                page_text.append(text)
                if flag_type is None:
                    clean_text.append(text)
                    continue
                page_flag_counts[flag_type] = page_flag_counts.get(flag_type, 0) + 1

            extracted_pages.append("".join(page_text))
            sanitized_pages.append("".join(clean_text))
            for flag_type, count in page_flag_counts.items():
                flags.append(
                    {
                        "type": flag_type,
                        "severity": "medium" if count < 100 else "high",
                        "page": page_index,
                        "details": f"Found {count} suspicious {flag_type.replace('_', ' ')} characters.",
                    }
                )
                removed.extend(_compact_snippets(chars, flag_type, page_index))

    warnings: list[dict] = []
    if flags:
        warnings.append(
            {
                "type": "sanitized_prompt_injection_risk",
                "message": (
                    "Found possible prompt injection or hidden resume content in white text/small "
                    "text. This content was removed before AI analysis."
                ),
            }
        )

    return TextExtractionResult(
        extracted_text="\n\n".join(page for page in extracted_pages if page.strip()),
        sanitized_text="\n\n".join(page for page in sanitized_pages if page.strip()),
        firewall_flags=flags,
        removed_suspicious_text=removed,
        parser_warnings=warnings,
    )

