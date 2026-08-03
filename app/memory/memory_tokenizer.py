"""Deterministic tokenization for keyword memory search."""

from __future__ import annotations

import re
import unicodedata

_TOKEN_PATTERN = re.compile(
    r"[^\W_]+",
    flags=re.UNICODE,
)


def normalize_search_text(text: str) -> str:
    """Normalize free text for keyword comparison."""

    normalized = unicodedata.normalize(
        "NFKC",
        text,
    )
    normalized = " ".join(normalized.split())

    return normalized.casefold()


def tokenize_memory_text(text: str) -> list[str]:
    """Return unique normalized tokens preserving order."""

    normalized = normalize_search_text(text)
    tokens = _TOKEN_PATTERN.findall(normalized)

    return list(dict.fromkeys(tokens))
