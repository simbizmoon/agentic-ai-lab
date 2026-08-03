"""Sanitization utilities for prompt memory context."""

from __future__ import annotations

import json


def truncate_memory_content(
    content: str,
    *,
    maximum_characters: int,
) -> str:
    """Truncate one memory value deterministically."""

    normalized = " ".join(content.split())

    if len(normalized) <= maximum_characters:
        return normalized

    return (
        normalized[
            : maximum_characters - 1
        ].rstrip()
        + "…"
    )


def encode_prompt_data(value: object) -> str:
    """Encode untrusted memory data as one JSON value."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return (
        encoded
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
