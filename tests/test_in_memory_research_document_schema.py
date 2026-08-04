"""Tests for in-memory research document records."""

import pytest
from pydantic import ValidationError

from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentReadMode,
    InMemoryResearchDocumentRecord,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
)


def record(
    **overrides: object,
) -> InMemoryResearchDocumentRecord:
    """Return one valid readable record."""

    values: dict[str, object] = {
        "source_id": "source-001",
        "url": "https://example.com/source",
        "content_type": ResearchSourceContentType.TEXT,
        "content": (
            "Agent memory stores contextual information."
        ),
        "language": "en",
        "read_mode": (
            InMemoryResearchDocumentReadMode.READABLE
        ),
        "metadata": {
            "collection": "test",
        },
    }
    values.update(overrides)

    return InMemoryResearchDocumentRecord.model_validate(
        values
    )


def test_readable_record_accepts_content() -> None:
    value = record()

    assert value.read_mode is (
        InMemoryResearchDocumentReadMode.READABLE
    )
    assert value.content


def test_readable_record_requires_content() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "readable record content must not be blank"
        ),
    ):
        record(content=" ")


def test_readable_record_rejects_failure_details() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "readable record must not contain "
            "failure_type"
        ),
    ):
        record(
            failure_type="UnexpectedFailure"
        )


def test_failing_record_accepts_failure_details() -> None:
    value = record(
        read_mode=InMemoryResearchDocumentReadMode.FAIL,
        content="",
        failure_type="AccessDenied",
        failure_message="The source denied access.",
        retryable=False,
    )

    assert value.failure_type == "AccessDenied"


def test_failing_record_requires_failure_type() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failing record must contain failure_type"
        ),
    ):
        record(
            read_mode=(
                InMemoryResearchDocumentReadMode.FAIL
            ),
            content="",
            failure_type=None,
            failure_message="Read failed.",
        )


def test_failing_record_requires_failure_message() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failing record must contain "
            "failure_message"
        ),
    ):
        record(
            read_mode=(
                InMemoryResearchDocumentReadMode.FAIL
            ),
            content="",
            failure_type="ReadFailure",
            failure_message=None,
        )


def test_failing_record_rejects_content() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failing record must not contain content"
        ),
    ):
        record(
            read_mode=(
                InMemoryResearchDocumentReadMode.FAIL
            ),
            content="Unexpected content",
            failure_type="ReadFailure",
            failure_message="Read failed.",
        )
