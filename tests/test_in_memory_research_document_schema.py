"""Tests for in-memory research document records."""

import pytest
from pydantic import ValidationError

from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentReadMode,
    InMemoryResearchDocumentRecord,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
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


def section(
    *,
    section_id: str = "section-custom",
    order: int = 1,
    start_character: int = 0,
    end_character: int = 12,
    content: str = "Agent memory",
) -> ResearchSourceDocumentSection:
    """Return one valid prebuilt document section."""

    return ResearchSourceDocumentSection(
        section_id=section_id,
        heading="Memory",
        content=content,
        order=order,
        start_character=start_character,
        end_character=end_character,
        metadata={"origin": "prebuilt"},
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


def test_readable_record_rejects_section_outside_content() -> None:
    with pytest.raises(
        ValidationError,
        match="section range must be within content",
    ):
        record(sections=[section(end_character=100)])


def test_readable_record_rejects_section_content_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match="section content must match its range",
    ):
        record(sections=[section(content="Wrong text")])


def test_readable_record_rejects_duplicate_section_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="section IDs must be unique",
    ):
        record(
            sections=[
                section(section_id="Page-A"),
                section(
                    section_id=" page-a ",
                    order=2,
                    start_character=13,
                    end_character=19,
                    content="stores",
                ),
            ]
        )


def test_readable_record_rejects_duplicate_section_orders() -> None:
    with pytest.raises(
        ValidationError,
        match="section orders must be unique",
    ):
        record(
            sections=[
                section(),
                section(
                    section_id="section-two",
                    start_character=13,
                    end_character=19,
                    content="stores",
                ),
            ]
        )


def test_readable_record_rejects_unordered_sections() -> None:
    with pytest.raises(
        ValidationError,
        match="sections must be ordered by order",
    ):
        record(
            sections=[
                section(section_id="section-two", order=2),
                section(
                    section_id="section-one",
                    order=1,
                    start_character=13,
                    end_character=19,
                    content="stores",
                ),
            ]
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


def test_failing_record_rejects_sections() -> None:
    with pytest.raises(
        ValidationError,
        match="failing record must not contain sections",
    ):
        record(
            read_mode=InMemoryResearchDocumentReadMode.FAIL,
            content="",
            sections=[section()],
            failure_type="AccessDenied",
            failure_message="The source denied access.",
        )


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
