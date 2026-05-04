"""Structured JSON logging setup."""
import logging
import logging.config

from pythonjsonlogger import jsonlogger


class JsonLogFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("logger", record.name)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


def setup_logging(log_level: str = "INFO", log_json: bool = True) -> None:
    formatter_class = (
        "app.shared.logging.JsonLogFormatter" if log_json else "logging.Formatter"
    )
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": formatter_class,
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s [request_id=%(request_id)s]",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["request_id_filter"],
                }
            },
            "filters": {
                "request_id_filter": {"()": "app.shared.logging.RequestIdFilter"}
            },
            "loggers": {
                "": {"handlers": ["console"], "level": log_level},
                "uvicorn": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
            },
        }
    )
