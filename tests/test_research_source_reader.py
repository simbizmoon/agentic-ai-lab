"""Tests for the research source reader contract."""

import pytest

from app.research.research_source_reader import (
    ResearchSourceReader,
)
from app.research.research_source_reader_validator import (
    ResearchSourceReaderValidator,
)
from app.schemas.research_request import (
    ResearchSourceType,
)
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentStatus,
)


def candidate(
    *,
    source_id: str = "source-001",
) -> ResearchSourceCandidate:
    """Return one valid source candidate."""

    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="research-001",
        task_id="task-001",
        query_id="query-001",
        title="Agent memory",
        url=f"https://example.com/{source_id}",
        source_type=ResearchSourceType.ACADEMIC,
        rank=1,
    )


class StubSourceReader(ResearchSourceReader):
    """Simple source reader for contract tests."""

    def __init__(
        self,
        *,
        name: str = "stub-reader",
    ) -> None:
        self._name = name

    @property
    def name(self) -> str:
        """Return the reader name."""

        return self._name

    def read(
        self,
        candidate: ResearchSourceCandidate,
    ) -> ResearchSourceDocument:
        """Return one deterministic document."""

        content = "Agent memory stores information."

        return ResearchSourceDocument(
            document_id=(
                f"document-{candidate.source_id}"
            ),
            candidate=candidate,
            status=ResearchSourceDocumentStatus.READ,
            content_type=ResearchSourceContentType.TEXT,
            content=content,
            sections=[],
            word_count=len(content.split()),
            character_count=len(content),
            reader=self.name,
        )


def test_reader_implements_contract() -> None:
    reader = StubSourceReader()
    value = candidate()

    document = reader.read(value)

    assert reader.name == "stub-reader"
    assert document.candidate == value
    assert document.reader == reader.name


def test_validator_accepts_reader_document() -> None:
    reader = StubSourceReader()
    value = candidate()
    document = reader.read(value)

    validator = ResearchSourceReaderValidator()

    validator.validate_reader(reader)
    validator.validate_document(
        reader=reader,
        candidate=value,
        document=document,
    )


def test_validator_rejects_blank_reader_name() -> None:
    reader = StubSourceReader(name=" ")

    with pytest.raises(
        ValueError,
        match=(
            "source reader name must not be blank"
        ),
    ):
        ResearchSourceReaderValidator().validate_reader(
            reader
        )


def test_validator_rejects_different_candidate() -> None:
    reader = StubSourceReader()
    original = candidate(source_id="source-001")
    different = candidate(source_id="source-002")
    document = reader.read(different)

    with pytest.raises(
        ValueError,
        match=(
            "document candidate must match "
            "the reader input candidate"
        ),
    ):
        ResearchSourceReaderValidator().validate_document(
            reader=reader,
            candidate=original,
            document=document,
        )


def test_validator_rejects_reader_name_mismatch() -> None:
    reader = StubSourceReader()
    value = candidate()
    content = "Agent memory stores information."

    document = ResearchSourceDocument(
        document_id="document-001",
        candidate=value,
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        sections=[],
        word_count=len(content.split()),
        character_count=len(content),
        reader="different-reader",
    )

    with pytest.raises(
        ValueError,
        match=(
            "document reader must match "
            "the source reader name"
        ),
    ):
        ResearchSourceReaderValidator().validate_document(
            reader=reader,
            candidate=value,
            document=document,
        )
