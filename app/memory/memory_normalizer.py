"""Deterministic normalization for memory comparison."""

from __future__ import annotations

import unicodedata


def normalize_memory_content(content: str) -> str:
    """Normalize memory content for exact duplicate comparison."""

    normalized = unicodedata.normalize(
        "NFKC",
        content,
    )
    normalized = " ".join(normalized.split())

    return normalized.casefold()


def normalize_memory_tags(
    tags: list[str],
) -> list[str]:
    """Normalize and sort tags for deterministic comparison."""

    return sorted(
        {
            unicodedata.normalize(
                "NFKC",
                tag.strip(),
            ).casefold()
            for tag in tags
            if tag.strip()
        }
    )
