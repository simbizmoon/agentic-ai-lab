"""Conservative publication-level identity for normalized patent records."""

from __future__ import annotations

import re

MAXIMUM_PUBLICATION_NUMBER_LENGTH = 128
_PUBLICATION_NUMBER_PATTERN = re.compile(r"[A-Z0-9./-]+", re.ASCII)


def normalize_patent_publication_number(publication_number: str) -> str:
    """Normalize only case and formatting-only ASCII whitespace.

    Punctuation is preserved because Step 1 does not assume worldwide patent
    numbering semantics. The function does not infer country, kind, family,
    or whether a value is a publication or application number.
    """

    if not isinstance(publication_number, str):
        raise TypeError("publication_number must be a string")

    normalized = "".join(publication_number.strip().split()).upper()
    if not normalized:
        raise ValueError("publication_number must not be blank")
    if len(normalized) > MAXIMUM_PUBLICATION_NUMBER_LENGTH:
        raise ValueError("publication_number is too long")
    if _PUBLICATION_NUMBER_PATTERN.fullmatch(normalized) is None:
        raise ValueError("publication_number contains unsupported characters")
    return normalized


def patent_publication_identity(publication_number: str) -> str:
    """Return deterministic identity from the normalized publication number."""

    normalized = normalize_patent_publication_number(publication_number)
    return f"publication-number:{normalized}"
