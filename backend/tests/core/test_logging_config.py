"""Unit tests for the logging redaction filter."""

import logging

import pytest

from app.core.logging_config import _RedactionFilter


def _make_record(msg: str, args: tuple = ()) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg=msg,
        args=args,
        exc_info=None,
    )
    return record


@pytest.mark.parametrize(
    "msg, args, should_be_absent",
    [
        # email inline
        ("Sign-in failed for user@example.com today", (), "user@example.com"),
        # email via %s args
        ("Sign-in failed for %s today", ("user@example.com",), "user@example.com"),
        # bearer token inline
        (
            "Auth header: Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig",
            (),
            "eyJhbGciOiJSUzI1NiJ9.payload.sig",
        ),
        # bearer token via %s args
        (
            "Auth header: %s",
            ("Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig",),
            "eyJhbGciOiJSUzI1NiJ9.payload.sig",
        ),
        # password inline
        ("Request body: password=s3cr3t!", (), "s3cr3t!"),
        # password via %s args
        ("Request body: %s", ("password=s3cr3t!",), "s3cr3t!"),
    ],
)
def test_redaction_filter_scrubs_secrets(
    msg: str, args: tuple, should_be_absent: str
) -> None:
    """Redaction filter must remove secrets and preserve surrounding text."""
    redaction_filter = _RedactionFilter()
    record = _make_record(msg=msg, args=args)
    result = redaction_filter.filter(record)

    assert result is True
    assert should_be_absent not in record.msg
    assert record.args is None


@pytest.mark.parametrize(
    "msg, surrounding_text",
    [
        ("Sign-in failed for user@example.com today", "Sign-in failed for"),
        ("Auth header: Bearer abc123", "Auth header:"),
        ("Request body: password=s3cr3t!", "Request body:"),
    ],
)
def test_redaction_filter_preserves_surrounding_text(
    msg: str, surrounding_text: str
) -> None:
    """Surrounding text must be preserved after redaction."""
    redaction_filter = _RedactionFilter()
    record = _make_record(msg=msg)
    redaction_filter.filter(record)

    assert surrounding_text in record.msg
