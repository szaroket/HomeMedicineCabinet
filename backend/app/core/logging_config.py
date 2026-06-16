"""Logging configuration: UTC timestamps, correlation IDs, structured format."""

import logging
import logging.config
import uuid
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


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


_FORMAT = (
    "[%(asctime)s][%(correlation_id)s][%(levelname)-8s] "
    "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
)

LOGGING_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": _CorrelationIdFilter,
        },
    },
    "formatters": {
        "standard": {
            "format": _FORMAT,
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "defaults": {"correlation_id": "-"},
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["correlation_id"],
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
        "uvicorn.access": {"propagate": True},
        "watchfiles": {"level": "WARNING", "propagate": False},
    },
}


def configure_logging() -> None:
    """Apply the logging configuration and force UTC timestamps.

    Call once at application startup before the first log statement.
    """
    logging.config.dictConfig(LOGGING_CONFIG)
    # Force all formatters to emit UTC rather than local time
    logging.Formatter.converter = __import__("time").gmtime


def generate_correlation_id() -> str:
    """Return a new short correlation ID (8 hex chars).

    Returns:
        str: A random 8-character hexadecimal string.
    """
    return uuid.uuid4().hex[:8]
