from __future__ import annotations

from typing import Any

import httpx

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_FALLBACK_MODELS = "gemini-3.5-flash,gemini-2.5-flash-lite,gemini-2.5-pro"
RETRYABLE_GEMINI_STATUS_CODES = {429, 500, 502, 503, 504}
MODEL_FALLBACK_STATUS_CODES = RETRYABLE_GEMINI_STATUS_CODES | {404}


def gemini_generate_content_url(model: str) -> str:
    return GEMINI_ENDPOINT.format(model=model)


def gemini_model_candidates(primary_model: str, fallback_models: str | None) -> list[str]:
    models: list[str] = []
    for raw_model in [primary_model, *(fallback_models or "").split(",")]:
        model = raw_model.strip()
        if model and model not in models:
            models.append(model)
    return models


def should_try_next_gemini_model(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in MODEL_FALLBACK_STATUS_CODES
    return isinstance(exc, httpx.HTTPError)


def describe_gemini_error(exc: Exception | None) -> str:
    if exc is None:
        return "temporary error"
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        status_text = f"{response.status_code} {response.reason_phrase}".strip()
        message = _extract_error_message(response)
        return f"Gemini request failed with status {status_text}" + (
            f": {message}" if message else ""
        )
    if isinstance(exc, httpx.HTTPError):
        return "Gemini request failed due to a network error"
    return str(exc)


def _extract_error_message(response: httpx.Response) -> str | None:
    try:
        payload: Any = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return None
