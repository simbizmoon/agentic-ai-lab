"""Tests for structured research request schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.research_request import (
    ResearchDepth,
    ResearchOutputFormat,
    ResearchRequest,
    ResearchSourceType,
)


def valid_request(
    **overrides: object,
) -> ResearchRequest:
    """Return one valid research request."""

    values: dict[str, object] = {
        "request_id": "research-001",
        "question": (
            "How do agent memory architectures differ?"
        ),
        "objective": (
            "Compare major memory patterns and identify "
            "their engineering trade-offs."
        ),
        "depth": ResearchDepth.DEEP,
        "output_format": (
            ResearchOutputFormat.COMPARISON
        ),
        "include_topics": [
            "working memory",
            "episodic memory",
        ],
        "exclude_topics": [
            "consumer hardware",
        ],
        "preferred_source_types": [
            ResearchSourceType.PRIMARY_RESEARCH,
            ResearchSourceType.OFFICIAL_DOCUMENTATION,
        ],
        "start_date": date(2024, 1, 1),
        "end_date": date(2026, 12, 31),
        "maximum_sources": 20,
        "require_citations": True,
        "metadata": {
            "project": "aira",
            "baseline": "single-agent",
        },
    }
    values.update(overrides)

    return ResearchRequest.model_validate(values)


def test_request_accepts_valid_values() -> None:
    request = valid_request()

    assert request.request_id == "research-001"
    assert request.depth is ResearchDepth.DEEP
    assert request.maximum_sources == 20
    assert request.require_citations is True


def test_request_uses_safe_defaults() -> None:
    request = ResearchRequest(
        request_id="research-002",
        question="What is retrieval-augmented generation?",
        objective="Explain the core architecture.",
    )

    assert request.depth is ResearchDepth.STANDARD
    assert request.output_format is (
        ResearchOutputFormat.DETAILED_REPORT
    )
    assert request.maximum_sources == 10
    assert request.require_citations is True
    assert request.include_topics == []
    assert request.exclude_topics == []
    assert request.preferred_source_types == []
    assert request.metadata == {}


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("request_id", " "),
        ("question", ""),
        ("objective", "\t"),
    ],
)
def test_request_rejects_blank_required_text(
    field_name: str,
    field_value: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field_name} must not be blank",
    ):
        valid_request(
            **{field_name: field_value}
        )


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ResearchRequest.model_validate(
            {
                "request_id": "research-001",
                "question": "A question",
                "objective": "An objective",
                "unknown_field": "not allowed",
            }
        )


def test_request_rejects_invalid_source_limit() -> None:
    with pytest.raises(ValidationError):
        valid_request(maximum_sources=0)

    with pytest.raises(ValidationError):
        valid_request(maximum_sources=101)


def test_request_rejects_reversed_date_range() -> None:
    with pytest.raises(
        ValidationError,
        match="start_date must not be after end_date",
    ):
        valid_request(
            start_date=date(2026, 1, 1),
            end_date=date(2025, 1, 1),
        )


def test_request_allows_open_date_range() -> None:
    request = valid_request(
        start_date=None,
        end_date=date(2026, 1, 1),
    )

    assert request.start_date is None
    assert request.end_date == date(2026, 1, 1)


def test_request_rejects_blank_topic() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "include_topics must not contain blank values"
        ),
    ):
        valid_request(
            include_topics=[
                "memory",
                " ",
            ]
        )


def test_request_rejects_normalized_duplicate_topics() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "include_topics must not contain duplicates"
        ),
    ):
        valid_request(
            include_topics=[
                "Working Memory",
                " working memory ",
            ]
        )


def test_request_rejects_scope_overlap() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "include_topics and exclude_topics "
            "must not overlap"
        ),
    ):
        valid_request(
            include_topics=["Agent Memory"],
            exclude_topics=[" agent memory "],
        )


def test_request_rejects_duplicate_source_types() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "preferred_source_types must not "
            "contain duplicates"
        ),
    ):
        valid_request(
            preferred_source_types=[
                ResearchSourceType.ACADEMIC,
                ResearchSourceType.ACADEMIC,
            ]
        )


def test_request_rejects_blank_metadata_key() -> None:
    with pytest.raises(
        ValidationError,
        match="metadata keys must not be blank",
    ):
        valid_request(
            metadata={" ": "value"}
        )


def test_request_rejects_blank_metadata_value() -> None:
    with pytest.raises(
        ValidationError,
        match="metadata values must not be blank",
    ):
        valid_request(
            metadata={"project": " "}
        )


def test_request_is_frozen() -> None:
    request = valid_request()

    with pytest.raises(ValidationError):
        request.maximum_sources = 30
