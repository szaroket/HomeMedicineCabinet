"""Shared utility functions."""

import re

# Keep unicode word characters (incl. Polish diacritics) and digits; everything
# else — whitespace and tsquery operators (& | ! ( ) : *) — is a token boundary.
# This is what makes the constructed tsquery injection-safe.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_MIN_QUERY_LENGTH = 2


def build_tsquery(query: str) -> str | None:
    """Build a safe prefix ``to_tsquery`` expression from raw user input.

    Splits the query into alphanumeric/word tokens (dropping any tsquery
    operator characters), appends ``:*`` to each for prefix matching, and joins
    them with ``&``. The result is bound as a parameter, never interpolated, so
    user input cannot inject tsquery syntax.

    Args:
        query (str): Raw user search string.

    Returns:
        str | None: A tsquery string (e.g. ``apap:* & forte:*``), or None when the query
        has fewer than two effective characters.
    """
    tokens = _TOKEN_RE.findall(query)
    if sum(len(token) for token in tokens) < _MIN_QUERY_LENGTH:
        return None
    return " & ".join(f"{token}:*" for token in tokens)
