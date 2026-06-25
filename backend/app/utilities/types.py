"""Shared types: query-string aliases and cross-layer value objects.

Query() must stay INSIDE Annotated (not a default value) or Pydantic constraints
are silently dropped — see lessons.md L-003.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, NamedTuple

from pydantic import StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DosagePeriod(StrEnum):
    """Dosage period values — must match the DB CHECK constraint exactly."""

    day = "day"
    week = "week"


class ResolvedUsage(NamedTuple):
    """Cleaned, validated usage values ready for persistence.

    Lives here (not in cabinet.schemas) so the crud layer can consume it without
    depending on the request/response schema module — see lessons.md / impl review F2.
    """

    is_used: bool
    dosage_times: int | None
    dosage_period: DosagePeriod | None
    dosage_amount: int | None
    dosage_start_date: date | None
    dosage_end_date: date | None
