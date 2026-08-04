"""Tests for research source document schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.research_request import (
    ResearchSourceType,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentError,
    ResearchSourceDocumentSection,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)

CONTENT = (
    "Agent memory stores contextual information. "
    "Episodic memory records prior experiences."
)


def candidate(
    *,
    source_id: str = "source-001",
    request_id: str = "research-001",
) -> ResearchSourceCandidate:
    """Return one valid source candidate."""

    return ResearchSourceCandidate(
        source_id=source_id,
        request_id=request_id,
        task_id="task-001",
        query_id="query-001",
        title="Agent memory research",
        url=f"https://example.com/{source_id}",
        source_type=(
            ResearchSourceType.PRIMARY_RESEARCH
        ),
        rank=1,
    )


def section() -> ResearchSourceDocumentSection:
    """Return one valid document section."""

    section_content = (
        "Agent memory stores contextual information."
    )

    return ResearchSourceDocumentSection(
        section_id="section-001",
        heading="Agent memory",
        content=section_content,
        order=1,
        start_character=0,
        end_character=len(section_content),
    )


def read_document(
    *,
    document_id: str = "document-001",
    source_id: str = "source-001",
    request_id: str = "research-001",
    sections: list[
        ResearchSourceDocumentSection
    ] | None = None,
    **overrides: object,
) -> ResearchSourceDocument:
    """Return one successfully read document."""

    values: dict[str, object] = {
        "document_id": document_id,
        "candidate": candidate(
            source_id=source_id,
            request_id=request_id,
        ),
        "status": ResearchSourceDocumentStatus.READ,
        "content_type": ResearchSourceContentType.TEXT,
        "content": CONTENT,
        "language": "en",
        "sections": (
            sections
            if sections is not None
            else [section()]
        ),
        "word_count": len(CONTENT.split()),
        "character_count": len(CONTENT),
        "reader": "in-memory-reader",
        "error": None,
        "metadata": {
            "encoding": "utf-8",
        },
    }
    values.update(overrides)

    return ResearchSourceDocument.model_validate(values)


def failed_document(
    *,
    document_id: str = "document-001",
    source_id: str = "source-001",
) -> ResearchSourceDocument:
    """Return one failed document read."""

    return ResearchSourceDocument(
        document_id=document_id,
        candidate=candidate(source_id=source_id),
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        content="",
        sections=[],
        word_count=0,
        character_count=0,
        reader="in-memory-reader",
        error=ResearchSourceDocumentError(
            error_type="DocumentUnavailable",
            message="The source could not be read.",
            retryable=False,
        ),
    )


def test_section_accepts_valid_values() -> None:
    value = section()

    assert value.section_id == "section-001"
    assert value.order == 1


def test_section_rejects_blank_content() -> None:
    with pytest.raises(
        ValidationError,
        match="section content must not be blank",
    ):
        ResearchSourceDocumentSection(
            section_id="section-001",
            content=" ",
            order=1,
            start_character=0,
            end_character=1,
        )


def test_section_rejects_invalid_character_range() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "end_character must be greater than "
            "start_character"
        ),
    ):
        ResearchSourceDocumentSection(
            section_id="section-001",
            content="Text",
            order=1,
            start_character=4,
            end_character=4,
        )


def test_read_document_accepts_valid_values() -> None:
    value = read_document()

    assert value.status is (
        ResearchSourceDocumentStatus.READ
    )
    assert value.word_count == len(CONTENT.split())
    assert value.character_count == len(CONTENT)


def test_read_document_requires_content() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "read document content must not be blank"
        ),
    ):
        read_document(
            content="",
            word_count=0,
            character_count=0,
            sections=[],
        )


def test_read_document_rejects_error() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "read document must not contain an error"
        ),
    ):
        read_document(
            error=ResearchSourceDocumentError(
                error_type="Unexpected",
                message="Unexpected error.",
            )
        )


def test_read_document_validates_character_count() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "character_count must match content length"
        ),
    ):
        read_document(character_count=1)


def test_read_document_validates_word_count() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "word_count must match content word count"
        ),
    ):
        read_document(word_count=1)


def test_read_document_rejects_duplicate_section_ids() -> None:
    first = section()
    second_content = "Episodic memory"

    second = ResearchSourceDocumentSection(
        section_id=" SECTION-001 ",
        heading="Episodic",
        content=second_content,
        order=2,
        start_character=(
            CONTENT.index(second_content)
        ),
        end_character=(
            CONTENT.index(second_content)
            + len(second_content)
        ),
    )

    with pytest.raises(
        ValidationError,
        match="section IDs must be unique",
    ):
        read_document(sections=[first, second])


def test_read_document_rejects_duplicate_orders() -> None:
    first = section()
    second_content = "Episodic memory"

    second = ResearchSourceDocumentSection(
        section_id="section-002",
        heading="Episodic",
        content=second_content,
        order=1,
        start_character=(
            CONTENT.index(second_content)
        ),
        end_character=(
            CONTENT.index(second_content)
            + len(second_content)
        ),
    )

    with pytest.raises(
        ValidationError,
        match="section orders must be unique",
    ):
        read_document(sections=[first, second])


def test_read_document_rejects_section_outside_content() -> None:
    invalid_section = ResearchSourceDocumentSection(
        section_id="section-001",
        content="Outside",
        order=1,
        start_character=len(CONTENT),
        end_character=len(CONTENT) + 7,
    )

    with pytest.raises(
        ValidationError,
        match=(
            "section character range must be "
            "within document content"
        ),
    ):
        read_document(sections=[invalid_section])


def test_read_document_rejects_section_content_mismatch() -> None:
    invalid_section = ResearchSourceDocumentSection(
        section_id="section-001",
        content="Wrong",
        order=1,
        start_character=0,
        end_character=5,
    )

    with pytest.raises(
        ValidationError,
        match=(
            "section content must match "
            "the document character range"
        ),
    ):
        read_document(sections=[invalid_section])


def test_failed_document_accepts_structured_error() -> None:
    value = failed_document()

    assert value.status is (
        ResearchSourceDocumentStatus.FAILED
    )
    assert value.error is not None


def test_failed_document_requires_error() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed document must contain an error"
        ),
    ):
        ResearchSourceDocument(
            document_id="document-001",
            candidate=candidate(),
            status=ResearchSourceDocumentStatus.FAILED,
            content_type=ResearchSourceContentType.OTHER,
            reader="in-memory-reader",
        )


def test_failed_document_rejects_content() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "failed document must not contain content"
        ),
    ):
        ResearchSourceDocument(
            document_id="document-001",
            candidate=candidate(),
            status=ResearchSourceDocumentStatus.FAILED,
            content_type=ResearchSourceContentType.OTHER,
            content="Unexpected content",
            word_count=2,
            character_count=18,
            reader="in-memory-reader",
            error=ResearchSourceDocumentError(
                error_type="Failure",
                message="Read failed.",
            ),
        )


def test_document_orders_sections() -> None:
    first_content = (
        "Agent memory stores contextual information."
    )
    second_content = (
        "Episodic memory records prior experiences."
    )

    second_start = CONTENT.index(second_content)

    value = read_document(
        sections=[
            ResearchSourceDocumentSection(
                section_id="section-002",
                content=second_content,
                order=2,
                start_character=second_start,
                end_character=(
                    second_start + len(second_content)
                ),
            ),
            ResearchSourceDocumentSection(
                section_id="section-001",
                content=first_content,
                order=1,
                start_character=0,
                end_character=len(first_content),
            ),
        ]
    )

    assert [
        item.section_id
        for item in value.ordered_sections()
    ] == [
        "section-001",
        "section-002",
    ]


def test_document_set_accepts_read_and_failed_documents() -> None:
    value = ResearchSourceDocumentSet(
        request_id="research-001",
        documents=[
            read_document(),
            failed_document(
                document_id="document-002",
                source_id="source-002",
            ),
        ],
    )

    assert len(value.successful_documents()) == 1
    assert len(value.failed_documents()) == 1


def test_document_set_rejects_duplicate_document_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="document IDs must be unique",
    ):
        ResearchSourceDocumentSet(
            request_id="research-001",
            documents=[
                read_document(
                    document_id="document-001",
                    source_id="source-001",
                ),
                read_document(
                    document_id=" DOCUMENT-001 ",
                    source_id="source-002",
                ),
            ],
        )


def test_document_set_rejects_duplicate_sources() -> None:
    with pytest.raises(
        ValidationError,
        match="document source IDs must be unique",
    ):
        ResearchSourceDocumentSet(
            request_id="research-001",
            documents=[
                read_document(
                    document_id="document-001",
                    source_id="source-001",
                ),
                read_document(
                    document_id="document-002",
                    source_id=" SOURCE-001 ",
                ),
            ],
        )


def test_document_set_rejects_request_mismatch() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "all document request IDs must match"
        ),
    ):
        ResearchSourceDocumentSet(
            request_id="research-001",
            documents=[
                read_document(
                    request_id="research-002"
                )
            ],
        )
