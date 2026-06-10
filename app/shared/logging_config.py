"""
Centralized structured logging configuration.

Provides:
- Request/user context propagation via contextvars
- PII sanitization filter
- JSON formatter for production (single-line, Twelve-Factor App)
- Colorized console output for local development
- setup_logging() to wire everything at app startup
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
import traceback as tb
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pythonjsonlogger.json import JsonFormatter as _BaseJsonFormatter

# ── Context variables ─────────────────────────────────────────────────────────

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def set_request_id(val: str) -> None:
    request_id_var.set(val)


def set_user_id(val: str | None) -> None:
    user_id_var.set(val)


def get_request_id() -> str:
    return request_id_var.get()


def get_user_id() -> str | None:
    return user_id_var.get()


# ── PII Sanitization ──────────────────────────────────────────────────────────

# Keys whose values should be masked
_SENSITIVE_KEY_PATTERNS = re.compile(
    r"(password|secret|token|credential|api_key|access_token|refresh_token|jwt|"
    r"authorization|auth)",
    re.IGNORECASE,
)

# Value patterns that look like JWTs
_JWT_PATTERN = re.compile(r"^eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$")


def _sanitize_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively mask sensitive values in a dictionary."""
    sanitized: dict[str, Any] = {}
    for key, value in d.items():
        if isinstance(value, dict):
            sanitized[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize_dict(v) if isinstance(v, dict) else v for v in value
            ]
        elif isinstance(value, str):
            if _SENSITIVE_KEY_PATTERNS.search(key):
                sanitized[key] = "***"
            elif _JWT_PATTERN.match(value):
                sanitized[key] = "[REDACTED JWT]"
            elif key.lower() == "authorization" and value.lower().startswith("bearer "):
                sanitized[key] = value[:17] + "..."
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value
    return sanitized


def _sanitize_extra(record: logging.LogRecord) -> None:
    """Sanitize the record's extra dict in-place."""
    if not hasattr(record, "extra") or not record.extra:  # type: ignore[attr-defined]
        return

    extra = record.extra  # type: ignore[attr-defined]
    if isinstance(extra, dict):
        record.extra = _sanitize_dict(dict(extra))  # type: ignore[attr-defined]


class PiiSanitizingFilter(logging.Filter):
    """Filter that sanitizes sensitive data from log records before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Sanitize the message string for inline sensitive content
        if isinstance(record.msg, str):
            record.msg = _JWT_PATTERN.sub("[REDACTED JWT]", record.msg)

        # Sanitize extras
        _sanitize_extra(record)

        return True


# ── JSON Formatter ────────────────────────────────────────────────────────────


class JsonLogFormatter(_BaseJsonFormatter):
    """Single-line JSON formatter with request_id, user_id, and structured exception info."""

    def __init__(self, **kwargs: Any) -> None:
        # Reserve the standard fields we control explicitly
        reserved = {
            "timestamp",
            "level",
            "logger",
            "message",
            "request_id",
            "user_id",
            "context",
            "exception",
        }
        super().__init__(
            fmt="%(timestamp)s %(level)s %(logger)s %(message)s",
            reserved_attrs=reserved,
            **kwargs,
        )

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        log_record["timestamp"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        log_record["logger"] = record.name
        log_record["request_id"] = get_request_id()

        user_id = get_user_id()
        if user_id is not None:
            log_record["user_id"] = user_id

        # Merge internal extras under "context"
        if hasattr(record, "extra") and record.extra:  # type: ignore[attr-defined]
            log_record["context"] = record.extra  # type: ignore[attr-defined]

        if record.exc_info and record.exc_info[0] is not None:
            exc_type = record.exc_info[0]
            exc_traceback = record.exc_info[2]
            log_record["exception"] = {
                "type": exc_type.__name__,
                "traceback": "".join(tb.format_tb(exc_traceback)),
            }

        # Clean up the default message field name to be just "message"
        if "message" in log_record:
            log_record["message"] = log_record.pop("message")


# ── Setup ─────────────────────────────────────────────────────────────────────


class _LevelRangeFilter(logging.Filter):
    """Allow records whose level is in [min_level, max_level] (inclusive)."""

    def __init__(self, min_level: int, max_level: int) -> None:
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return self.min_level <= record.levelno <= self.max_level


def setup_logging(settings: Any) -> None:
    """
    Configure the root logger based on environment mode.

    - DEBUG mode: colorized console + ./logs/app_errors.log (ERROR+)
    - Production mode: JSON stdout (INFO-) + JSON stderr (WARN+)
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    pii_filter = PiiSanitizingFilter()

    if getattr(settings, "debug", False):
        # ── Development ──────────────────────────────────────────────────

        # Console handler with colorized human-readable output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.addFilter(pii_filter)
        console_handler.setLevel(root_logger.level)
        console_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_fmt)
        root_logger.addHandler(console_handler)

        # Error file handler
        log_dir = Path(getattr(settings, "log_dir", "./logs"))
        log_dir.mkdir(parents=True, exist_ok=True)

        error_handler = logging.FileHandler(str(log_dir / "app_errors.log"))
        error_handler.addFilter(pii_filter)
        error_handler.setLevel(logging.ERROR)
        error_fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        error_handler.setFormatter(error_fmt)
        root_logger.addHandler(error_handler)

    else:
        # ── Production ───────────────────────────────────────────────────
        json_formatter = JsonLogFormatter()

        # stdout: DEBUG and INFO only
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.addFilter(pii_filter)
        stdout_handler.addFilter(_LevelRangeFilter(logging.DEBUG, logging.INFO))
        stdout_handler.setFormatter(json_formatter)
        root_logger.addHandler(stdout_handler)

        # stderr: WARNING and above
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.addFilter(pii_filter)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(json_formatter)
        root_logger.addHandler(stderr_handler)

    # Quiet down noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
