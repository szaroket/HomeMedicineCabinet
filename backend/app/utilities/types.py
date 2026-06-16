"""Shared type aliases for query-string parameters.

Query() must stay INSIDE Annotated (not a default value) or Pydantic constraints
are silently dropped — see lessons.md L-003.
"""

from typing import Annotated

from pydantic import StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
