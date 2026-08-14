"""Tests for the in-memory research source reader."""

import pytest

from app.research.in_memory_research_source_reader import (
    InMemoryResearchSourceReader,
)
from app.research.research_source_reader_validator import (
    ResearchSourceReaderValidator,
)
from app.schemas.in_memory_research_document import (
    InMemoryResearchDocumentReadMode,
    InMemoryResearchDocumentRecord,
)
from app.schemas.research_request import (
    ResearchSourceType,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocumentSection,
    ResearchSourceDocumentStatus,
)

CONTENT = (
    "Agent memory stores contextual information.\n\n"
    "Episodic memory records prior experiences."
)


def candidate(
    *,
    source_id: str = "source-001",
    url: str = "https://example.com/source",
) -> ResearchSourceCandidate:
    """Return one source candidate."""

    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="research-001",
        task_id="task-001",
        query_id="query-001",
        title="Agent memory",
        url=url,
        source_type=ResearchSourceType.ACADEMIC,
        rank=1,
    )


def readable_record(
    *,
    source_id: str = "source-001",
    url: str = "https://example.com/source",
    sections: list[ResearchSourceDocumentSection] | None = None,
) -> InMemoryResearchDocumentRecord:
    """Return one readable document record."""

    return InMemoryResearchDocumentRecord(
        source_id=source_id,
        url=url,
        content_type=ResearchSourceContentType.TEXT,
        content=CONTENT,
        language="en",
        sections=sections or [],
        metadata={
            "collection": "test",
        },
    )


def prebuilt_sections() -> list[ResearchSourceDocumentSection]:
    """Return ordered non-contiguous prebuilt sections."""

    second_start = CONTENT.index("Episodic")
    return [
        ResearchSourceDocumentSection(
            section_id="page-alpha",
            heading="First page",
            content=CONTENT[:12],
            order=1,
            start_character=0,
            end_character=12,
            metadata={"page_number": "1"},
        ),
        ResearchSourceDocumentSection(
            section_id="page-charlie",
            heading=None,
            content=CONTENT[second_start:],
            order=2,
            start_character=second_start,
            end_character=len(CONTENT),
            metadata={"page_number": "3"},
        ),
    ]


def reader() -> InMemoryResearchSourceReader:
    """Return one in-memory reader."""

    return InMemoryResearchSourceReader(
        records=[readable_record()]
    )


def test_reader_returns_read_document() -> None:
    value = reader()
    source = candidate()

    document = value.read(source)

    assert document.status is (
        ResearchSourceDocumentStatus.READ
    )
    assert document.content == CONTENT
    assert document.word_count == len(CONTENT.split())
    assert document.character_count == len(CONTENT)


def test_reader_builds_ordered_sections() -> None:
    document = reader().read(candidate())

    assert [
        section.section_id
        for section in document.sections
    ] == [
        "section-001",
        "section-002",
    ]

    assert [
        section.content
        for section in document.sections
    ] == [
        "Agent memory stores contextual information.",
        "Episodic memory records prior experiences.",
    ]


def test_reader_preserves_prebuilt_sections() -> None:
    sections = prebuilt_sections()
    value = InMemoryResearchSourceReader(
        records=[readable_record(sections=sections)]
    )

    document = value.read(candidate())

    assert [item.section_id for item in document.sections] == [
        "page-alpha",
        "page-charlie",
    ]
    assert [item.heading for item in document.sections] == [
        "First page",
        None,
    ]
    assert [item.order for item in document.sections] == [1, 2]
    assert [
        (item.start_character, item.end_character)
        for item in document.sections
    ] == [
        (0, 12),
        (CONTENT.index("Episodic"), len(CONTENT)),
    ]
    assert [item.metadata["page_number"] for item in document.sections] == [
        "1",
        "3",
    ]
    assert "section-001" not in {
        item.section_id for item in document.sections
    }


def test_reader_defensively_copies_prebuilt_sections() -> None:
    value = InMemoryResearchSourceReader(
        records=[readable_record(sections=prebuilt_sections())]
    )

    first = value.read(candidate())
    first.sections[0].metadata["page_number"] = "changed"
    second = value.read(candidate())

    assert second.sections[0].metadata["page_number"] == "1"


def test_reader_section_ranges_match_content() -> None:
    document = reader().read(candidate())

    for section in document.sections:
        assert document.content[
            section.start_character:
            section.end_character
        ] == section.content


def test_reader_returns_not_found_failure() -> None:
    document = reader().read(
        candidate(
            source_id="missing-source",
            url="https://example.com/missing",
        )
    )

    assert document.status is (
        ResearchSourceDocumentStatus.FAILED
    )
    assert document.error is not None
    assert document.error.error_type == (
        "DocumentNotFound"
    )


def test_reader_returns_url_mismatch_failure() -> None:
    document = reader().read(
        candidate(
            url="https://example.com/different"
        )
    )

    assert document.status is (
        ResearchSourceDocumentStatus.FAILED
    )
    assert document.error is not None
    assert document.error.error_type == (
        "SourceUrlMismatch"
    )


def test_reader_returns_configured_failure() -> None:
    failing_record = InMemoryResearchDocumentRecord(
        source_id="source-001",
        url="https://example.com/source",
        content_type=ResearchSourceContentType.OTHER,
        content="",
        read_mode=(
            InMemoryResearchDocumentReadMode.FAIL
        ),
        failure_type="AccessDenied",
        failure_message="The source denied access.",
        retryable=False,
    )

    value = InMemoryResearchSourceReader(
        records=[failing_record]
    )

    document = value.read(candidate())

    assert document.status is (
        ResearchSourceDocumentStatus.FAILED
    )
    assert document.error is not None
    assert document.error.error_type == "AccessDenied"


def test_reader_output_satisfies_contract_validator() -> None:
    value = reader()
    source = candidate()
    document = value.read(source)

    ResearchSourceReaderValidator().validate_document(
        reader=value,
        candidate=source,
        document=document,
    )


def test_reader_is_deterministic() -> None:
    value = reader()
    source = candidate()

    first = value.read(source)
    second = value.read(source)

    assert (
        first.model_dump(mode="json")
        == second.model_dump(mode="json")
    )


def test_reader_returns_defensive_record_copies() -> None:
    value = reader()

    returned = value.records()
    returned.clear()

    assert len(value.records()) == 1


def test_reader_rejects_duplicate_source_ids() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "document record source IDs must be unique"
        ),
    ):
        InMemoryResearchSourceReader(
            records=[
                readable_record(
                    source_id="source-001",
                    url="https://example.com/first",
                ),
                readable_record(
                    source_id=" SOURCE-001 ",
                    url="https://example.com/second",
                ),
            ]
        )


def test_reader_rejects_duplicate_urls() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "document record URLs must be unique"
        ),
    ):
        InMemoryResearchSourceReader(
            records=[
                readable_record(
                    source_id="source-001",
                    url="https://example.com/source/",
                ),
                readable_record(
                    source_id="source-002",
                    url=(
                        "HTTPS://EXAMPLE.COM:443/source"
                    ),
                ),
            ]
        )


def test_reader_rejects_blank_name() -> None:
    with pytest.raises(
        ValueError,
        match="name must not be blank",
    ):
        InMemoryResearchSourceReader(
            records=[],
            name=" ",
        )
