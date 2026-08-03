"""Deterministic detection of obvious sensitive memory content."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SensitiveMemoryMatch:
    """One detected sensitive-content category."""

    category: str
    matched_text: str


_SECRET_PATTERNS: tuple[
    tuple[str, re.Pattern[str]],
    ...,
] = (
    (
        "openai_api_key",
        re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    ),
    (
        "github_token",
        re.compile(
            r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"
        ),
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?"
            r"PRIVATE KEY-----"
        ),
    ),
    (
        "password_assignment",
        re.compile(
            r"\b(?:password|passwd|pwd)\s*[:=]\s*"
            r"\S+",
            re.IGNORECASE,
        ),
    ),
)

_SENSITIVE_PATTERNS: tuple[
    tuple[str, re.Pattern[str]],
    ...,
] = (
    (
        "korean_resident_number",
        re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)"),
    ),
    (
        "credit_card_number",
        re.compile(
            r"\b(?:\d[ -]*?){13,19}\b"
        ),
    ),
)


def detect_secret_content(
    content: str,
) -> list[SensitiveMemoryMatch]:
    """Return obvious secret values found in content."""

    return _find_matches(
        content=content,
        patterns=_SECRET_PATTERNS,
    )


def detect_sensitive_content(
    content: str,
) -> list[SensitiveMemoryMatch]:
    """Return obvious personal or financial identifiers."""

    return _find_matches(
        content=content,
        patterns=_SENSITIVE_PATTERNS,
    )


def _find_matches(
    *,
    content: str,
    patterns: tuple[
        tuple[str, re.Pattern[str]],
        ...,
    ],
) -> list[SensitiveMemoryMatch]:
    """Return deterministic pattern matches."""

    matches: list[SensitiveMemoryMatch] = []

    for category, pattern in patterns:
        match = pattern.search(content)

        if match is not None:
            matches.append(
                SensitiveMemoryMatch(
                    category=category,
                    matched_text=match.group(0),
                )
            )

    return matches
