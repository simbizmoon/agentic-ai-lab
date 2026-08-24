"""Offline tests for deterministic cross-source chunk ingestion."""

from __future__ import annotations

from typing import Any

import pytest

from app.rag.document_chunker import chunk_document_by_paragraphs
from app.research.cross_source_chunk_ingestion_runtime import (
    CrossSourceChunkIngestionRuntime,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateStatus,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentError,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)


def _candidate(
    source_id: str, source_type: ResearchSourceType, rank: int
) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="request-1",
        task_id=f"task-{rank}",
        query_id=f"query-{rank}",
        title=f"Source {rank}",
        url=f"https://example.com/{rank}",
        source_type=source_type,
        rank=rank,
        status=ResearchSourceCandidateStatus.READ,
    )


def _read_document(
    document_id: str,
    source_id: str,
    source_type: ResearchSourceType,
    rank: int,
    content: str,
) -> ResearchSourceDocument:
    return ResearchSourceDocument(
        document_id=document_id,
        candidate=_candidate(source_id, source_type, rank),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="fixture-reader",
    )


def _document_set() -> ResearchSourceDocumentSet:
    failed = ResearchSourceDocument(
        document_id="document-failed",
        candidate=_candidate("source-failed", ResearchSourceType.NEWS, 3),
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        reader="fixture-reader",
        error=ResearchSourceDocumentError(
            error_type="ReadError",
            message="fixture failure",
            retryable=False,
        ),
    )
    return ResearchSourceDocumentSet(
        request_id="request-1",
        documents=[
            _read_document(
                "document-academic",
                "source-academic",
                ResearchSourceType.ACADEMIC,
                1,
                "Academic first paragraph.\n\nAcademic second paragraph.",
            ),
            failed,
            _read_document(
                "document-official",
                "source-official",
                ResearchSourceType.OFFICIAL_DOCUMENTATION,
                2,
                "Official guidance paragraph.",
            ),
        ],
    )


def test_ingests_multiple_source_types_with_exact_provenance() -> None:
    document_set = _document_set()
    result = CrossSourceChunkIngestionRuntime(
        chunk_size=30,
        chunk_overlap=5,
    ).ingest(document_set=document_set)

    assert [item.document_id for item in result.ordered_chunks()] == [
        "document-academic",
        "document-academic",
        "document-official",
    ]
    assert result.failed_document_ids == ["document-failed"]
    assert len(result.chunks) == len(result.provenance) == 3

    documents = {item.document_id: item for item in document_set.documents}
    links = {item.chunk_id: item for item in result.provenance}
    for chunk in result.chunks:
        document = documents[chunk.document_id]
        link = links[chunk.chunk_id]
        assert chunk.text == document.content[chunk.start_char : chunk.end_char]
        assert link.source_id == document.candidate.source_id
        assert link.source_type is document.candidate.source_type
        assert (link.start_character, link.end_character) == (
            chunk.start_char,
            chunk.end_char,
        )


def test_attaches_retrieval_identity_metadata_to_every_chunk() -> None:
    result = CrossSourceChunkIngestionRuntime(
        chunk_size=100,
        chunk_overlap=10,
    ).ingest(document_set=_document_set())

    academic = next(
        item for item in result.chunks if item.document_id == "document-academic"
    )
    assert academic.metadata == {
        "request_id": "request-1",
        "task_id": "task-1",
        "source_id": "source-academic",
        "source_type": "academic",
    }


def test_failed_documents_are_not_sent_to_chunker() -> None:
    calls: list[str] = []

    def recording_chunker(**arguments: Any) -> list[DocumentChunk]:
        calls.append(arguments["document_id"])
        return chunk_document_by_paragraphs(**arguments)

    result = CrossSourceChunkIngestionRuntime(
        chunk_size=100,
        chunk_overlap=10,
        chunker=recording_chunker,
    ).ingest(document_set=_document_set())

    assert calls == ["document-academic", "document-official"]
    assert result.failed_document_ids == ["document-failed"]


def test_same_input_produces_same_chunks_and_provenance() -> None:
    runtime = CrossSourceChunkIngestionRuntime(chunk_size=30, chunk_overlap=5)
    document_set = _document_set()

    first = runtime.ingest(document_set=document_set)
    second = runtime.ingest(document_set=document_set)

    assert first == second


def test_empty_document_set_produces_empty_result() -> None:
    result = CrossSourceChunkIngestionRuntime().ingest(
        document_set=ResearchSourceDocumentSet(
            request_id="request-empty",
            documents=[],
        )
    )

    assert result.chunks == []
    assert result.provenance == []
    assert result.failed_document_ids == []


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap", "message"),
    [
        (0, 0, "chunk_size must be greater"),
        (10, -1, "chunk_overlap must not be negative"),
        (10, 10, "chunk_overlap must be smaller"),
        (10, 11, "chunk_overlap must be smaller"),
    ],
)
def test_rejects_invalid_chunk_configuration(
    chunk_size: int,
    chunk_overlap: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CrossSourceChunkIngestionRuntime(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )


def test_contract_rejects_corrupt_chunker_output() -> None:
    def corrupt_chunker(**arguments: Any) -> list[DocumentChunk]:
        return [
            DocumentChunk(
                document_id=arguments["document_id"],
                chunk_id=f"{arguments['document_id']}:chunk:0000",
                ordinal=0,
                text="X",
                start_char=0,
                end_char=1,
                metadata=arguments["metadata"],
            )
        ]

    runtime = CrossSourceChunkIngestionRuntime(chunker=corrupt_chunker)
    with pytest.raises(ValueError, match="exact document character range"):
        runtime.ingest(document_set=_document_set())
