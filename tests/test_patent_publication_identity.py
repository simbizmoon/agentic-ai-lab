"""Tests for conservative patent publication identity."""

import pytest

from app.research.patent_publication_identity import (
    normalize_patent_publication_number,
    patent_publication_identity,
)


def test_normalizer_removes_formatting_whitespace_and_normalizes_case() -> None:
    assert normalize_patent_publication_number("  wo 2024/123456 a1  ") == (
        "WO2024/123456A1"
    )


def test_identity_is_deterministic() -> None:
    first = patent_publication_identity("WO 2024/123456 A1")
    second = patent_publication_identity("wo2024/123456a1")

    assert first == second == "publication-number:WO2024/123456A1"


@pytest.mark.parametrize("value", ["", "  ", "\t\n"])
def test_normalizer_rejects_blank_values(value: str) -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_patent_publication_number(value)


def test_normalizer_preserves_punctuation_and_does_not_infer_parts() -> None:
    assert normalize_patent_publication_number("2024-123.4") == "2024-123.4"
    assert normalize_patent_publication_number("123456") == "123456"
    assert normalize_patent_publication_number("123456") != (
        normalize_patent_publication_number("WO123456A1")
    )


def test_distinct_publication_numbers_remain_distinct() -> None:
    assert patent_publication_identity("WO2024/123456A1") != (
        patent_publication_identity("WO2024/123456A2")
    )
    assert patent_publication_identity("WO2024/123456A1") != (
        patent_publication_identity("WO2024-123456A1")
    )


def test_identity_uses_no_title_or_fuzzy_matching() -> None:
    identity = patent_publication_identity("WO2024/123456A1")

    assert identity == "publication-number:WO2024/123456A1"
    assert "title" not in identity


def test_normalizer_rejects_unsafe_or_unreasonably_long_values() -> None:
    with pytest.raises(ValueError, match="unsupported characters"):
        normalize_patent_publication_number("WO2024:123456")
    with pytest.raises(ValueError, match="too long"):
        normalize_patent_publication_number("A" * 129)
