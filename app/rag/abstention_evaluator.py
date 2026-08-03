"""Deterministic detection of insufficient-evidence answers."""

from __future__ import annotations

from collections.abc import Sequence

DEFAULT_ABSTENTION_MARKERS: tuple[str, ...] = (
    "근거가 부족",
    "근거만으로는",
    "답변할 수 없",
    "확인할 수 없",
    "정보가 부족",
    "제공된 정보",
    "insufficient evidence",
    "cannot answer",
    "not enough information",
)


def normalize_answer_text(text: str) -> str:
    """Normalize answer text for marker matching."""

    return " ".join(text.casefold().split())


def find_abstention_markers(
    *,
    answer_text: str,
    markers: Sequence[str] = DEFAULT_ABSTENTION_MARKERS,
) -> list[str]:
    """Return abstention markers found in an answer."""

    normalized_answer = normalize_answer_text(answer_text)
    matched: list[str] = []

    for marker in markers:
        normalized_marker = normalize_answer_text(marker)

        if (
            normalized_marker
            and normalized_marker in normalized_answer
            and marker not in matched
        ):
            matched.append(marker)

    return matched


def is_abstention_answer(
    *,
    answer_text: str,
    markers: Sequence[str] = DEFAULT_ABSTENTION_MARKERS,
) -> bool:
    """Return whether an answer explicitly reports insufficient evidence."""

    return bool(
        find_abstention_markers(
            answer_text=answer_text,
            markers=markers,
        )
    )
