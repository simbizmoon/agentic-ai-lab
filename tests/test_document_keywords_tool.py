"""Tests for deterministic document keyword extraction."""

import pytest
from pydantic import ValidationError

from app.tools.document_keywords import (
    DocumentKeywordsInput,
    extract_document_keywords,
)


def test_extracts_keywords_by_frequency() -> None:
    result = extract_document_keywords(
        DocumentKeywordsInput(
            document_text=(
                "agent tool agent workflow tool agent"
            ),
            max_keywords=3,
        )
    )

    assert result.model_dump() == {
        "keywords": [
            {
                "keyword": "agent",
                "count": 3,
            },
            {
                "keyword": "tool",
                "count": 2,
            },
            {
                "keyword": "workflow",
                "count": 1,
            },
        ]
    }


def test_uses_alphabetical_order_for_equal_counts() -> None:
    result = extract_document_keywords(
        DocumentKeywordsInput(
            document_text="zebra apple moon",
            max_keywords=3,
        )
    )

    assert [
        item.keyword
        for item in result.keywords
    ] == [
        "apple",
        "moon",
        "zebra",
    ]


def test_normalizes_case() -> None:
    result = extract_document_keywords(
        DocumentKeywordsInput(
            document_text="Agent AGENT agent",
            max_keywords=5,
        )
    )

    assert result.model_dump() == {
        "keywords": [
            {
                "keyword": "agent",
                "count": 3,
            }
        ]
    }


def test_supports_korean_words() -> None:
    result = extract_document_keywords(
        DocumentKeywordsInput(
            document_text=(
                "에이전트 도구 에이전트 워크플로"
            ),
            max_keywords=3,
        )
    )

    assert result.model_dump() == {
        "keywords": [
            {
                "keyword": "에이전트",
                "count": 2,
            },
            {
                "keyword": "도구",
                "count": 1,
            },
            {
                "keyword": "워크플로",
                "count": 1,
            },
        ]
    }


def test_limits_number_of_keywords() -> None:
    result = extract_document_keywords(
        DocumentKeywordsInput(
            document_text="one two three four",
            max_keywords=2,
        )
    )

    assert len(result.keywords) == 2


def test_rejects_whitespace_only_text() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain only whitespace",
    ):
        DocumentKeywordsInput(
            document_text="   ",
            max_keywords=5,
        )


def test_rejects_invalid_max_keywords() -> None:
    with pytest.raises(ValidationError):
        DocumentKeywordsInput(
            document_text="valid text",
            max_keywords=0,
        )


def test_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DocumentKeywordsInput.model_validate(
            {
                "document_text": "valid text",
                "max_keywords": 5,
                "unexpected": True,
            }
        )
