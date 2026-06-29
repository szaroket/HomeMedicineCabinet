"""Logging configuration: UTC timestamps, correlation IDs, structured format."""

import json
import logging
import logging.config
import re
import uuid
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TOKEN = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+")
_PASSWORD = re.compile(r"(?i)(password['\"]?\s*[:=]\s*)\S+")


class _CorrelationIdFilter(logging.Filter):
    """Inject the current request's correlation ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id attribute to the record.

        Args:
            record (logging.LogRecord): The log record being emitted.

        Returns:
            bool: Always True — this filter never suppresses records.
        """
        record.correlation_id = correlation_id_var.get()
        return True


class _RedactionFilter(logging.Filter):
    """Scrub PII and secrets from every emitted log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Render the full message and replace secrets with [REDACTED].

        Args:
            record (logging.LogRecord): The log record being emitted.

        Returns:
            bool: Always True — this filter never suppresses records.
        """
        message = record.getMessage()
        message = _EMAIL.sub("[REDACTED]", message)
        message = _TOKEN.sub(r"\1[REDACTED]", message)
        message = _PASSWORD.sub(r"\1[REDACTED]", message)
        record.msg = message
        record.args = None
        return True


_LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}
_RESET = "\033[0m"


class _ColoredConsoleFormatter(logging.Formatter):
    """Console formatter that colorizes the log level name."""

    def format(self, record: logging.LogRecord) -> str:
        """Apply ANSI color to levelname before delegating to standard format.

        Args:
            record (logging.LogRecord): The log record being emitted.

        Returns:
            str: Formatted log line with colorized level.
        """
        color = _LEVEL_COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{_RESET}"
        return super().format(record)


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record to JSON.

        Args:
            record (logging.LogRecord): The log record being emitted.

        Returns:
            str: A JSON string representation of the record.
        """
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "correlation_id": getattr(record, "correlation_id", "-"),
            "logger": f"{record.module}:{record.funcName}:{record.lineno}",
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


_CONSOLE_FORMAT = (
    "[%(asctime)s][%(correlation_id)-8s][%(levelname)-8s] "
    "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
)

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": _CorrelationIdFilter,
        },
        "redaction": {
            "()": _RedactionFilter,
        },
    },
    "formatters": {
        "console": {
            "()": _ColoredConsoleFormatter,
            "format": _CONSOLE_FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "defaults": {"correlation_id": "-"},
        },
        "json": {
            "()": _JsonFormatter,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "filters": ["correlation_id", "redaction"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "app": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "uvicorn.error": {"propagate": True},
        # Route through our handler so access lines use the same format/redaction
        "uvicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "watchfiles": {"level": "WARNING", "propagate": False},
    },
}


def configure_logging() -> None:
    """Apply the logging configuration and force UTC timestamps.

    Reads log_level and log_format from Settings to make output env-driven.
    Call once at application startup before the first log statement.
    """
    from app.core.config import settings

    config = dict(LOGGING_CONFIG)
    config["handlers"] = dict(LOGGING_CONFIG["handlers"])
    config["handlers"]["console"] = dict(LOGGING_CONFIG["handlers"]["console"])
    config["handlers"]["console"]["formatter"] = settings.log_format

    config["root"] = dict(LOGGING_CONFIG["root"])
    config["root"]["level"] = settings.log_level

    config["loggers"] = dict(LOGGING_CONFIG["loggers"])
    config["loggers"]["app"] = dict(LOGGING_CONFIG["loggers"].get("app", {}))
    config["loggers"]["app"]["level"] = settings.log_level

    logging.config.dictConfig(config)
    # Force all formatters to emit UTC rather than local time
    logging.Formatter.converter = __import__("time").gmtime


def generate_correlation_id() -> str:
    """Return a new short correlation ID (8 hex chars).

    Returns:
        str: A random 8-character hexadecimal string.
    """
    return uuid.uuid4().hex[:8]
