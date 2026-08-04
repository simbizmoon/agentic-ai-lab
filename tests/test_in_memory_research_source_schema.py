"""Tests for in-memory research source records."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.in_memory_research_source import (
    InMemoryResearchSourceRecord,
)
from app.schemas.research_request import (
    ResearchSourceType,
)


def record(
    **overrides: object,
) -> InMemoryResearchSourceRecord:
    """Return one valid in-memory source record."""

    values: dict[str, object] = {
        "source_id": "source-001",
        "title": "Agent memory architectures",
        "url": "https://example.com/memory",
        "source_type": (
            ResearchSourceType.PRIMARY_RESEARCH
        ),
        "snippet": (
            "A study comparing memory systems for agents."
        ),
        "keywords": [
            "agent memory",
            "working memory",
        ],
        "author": "Example Author",
        "publisher": "Example Publisher",
        "published_at": date(2026, 1, 10),
        "metadata": {
            "collection": "test",
        },
    }
    values.update(overrides)

    return InMemoryResearchSourceRecord.model_validate(
        values
    )


def test_record_accepts_valid_values() -> None:
    value = record()

    assert value.source_id == "source-001"
    assert len(value.keywords) == 2


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("source_id", " "),
        ("title", ""),
        ("url", "\t"),
    ],
)
def test_record_rejects_blank_required_text(
    field_name: str,
    field_value: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        record(
            **{field_name: field_value}
        )


def test_record_rejects_unsupported_url() -> None:
    with pytest.raises(
        ValidationError,
        match="url must use http or https",
    ):
        record(
            url="file:///tmp/source.txt"
        )


def test_record_rejects_blank_keyword() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "keywords must not contain blank values"
        ),
    ):
        record(
            keywords=[
                "agent memory",
                " ",
            ]
        )


def test_record_rejects_duplicate_keywords() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "keywords must not contain duplicates"
        ),
    ):
        record(
            keywords=[
                "Agent Memory",
                " agent memory ",
            ]
        )


def test_record_rejects_blank_optional_text() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "publisher must not be blank when provided"
        ),
    ):
        record(publisher=" ")
