"""Tests for deterministic memory normalization."""

from app.memory.memory_normalizer import (
    normalize_memory_content,
    normalize_memory_tags,
)


def test_content_normalizes_case_and_whitespace() -> None:
    assert normalize_memory_content(
        "  User   PREFERS\nverified commands. "
    ) == "user prefers verified commands."


def test_content_normalizes_unicode_compatibility() -> None:
    assert normalize_memory_content(
        "ＡＩＲＡ"
    ) == "aira"


def test_tags_are_normalized_sorted_and_unique() -> None:
    assert normalize_memory_tags(
        [
            " Workflow ",
            "preference",
            "WORKFLOW",
        ]
    ) == [
        "preference",
        "workflow",
    ]


def test_blank_tags_are_removed() -> None:
    assert normalize_memory_tags(
        ["workflow", " ", ""]
    ) == ["workflow"]
