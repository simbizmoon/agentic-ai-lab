"""Tests for deterministic keyword tokenization."""

from app.memory.memory_tokenizer import (
    normalize_search_text,
    tokenize_memory_text,
)


def test_normalizes_case_and_whitespace() -> None:
    assert normalize_search_text(
        "  VERIFIED\n Commands "
    ) == "verified commands"


def test_normalizes_unicode_compatibility() -> None:
    assert normalize_search_text(
        "ＡＩＲＡ"
    ) == "aira"


def test_tokenizes_english_and_numbers() -> None:
    assert tokenize_memory_text(
        "AIRA uses 256 dimensions."
    ) == [
        "aira",
        "uses",
        "256",
        "dimensions",
    ]


def test_tokenizes_korean_text() -> None:
    assert tokenize_memory_text(
        "사용자는 검증된 명령을 선호한다."
    ) == [
        "사용자는",
        "검증된",
        "명령을",
        "선호한다",
    ]


def test_tokens_are_unique_preserving_order() -> None:
    assert tokenize_memory_text(
        "memory search memory"
    ) == [
        "memory",
        "search",
    ]
