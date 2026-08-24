"""Offline tests for cross-source chunk ingestion contracts."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.schemas.cross_source_chunk_ingestion import (
    CrossSourceChunkIngestionResult,
    CrossSourceChunkProvenance,
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
        task_id="task-1",
        query_id="query-1",
        title=f"Source {rank}",
        url=f"https://example.com/source-{rank}",
        source_type=source_type,
        rank=rank,
        status=ResearchSourceCandidateStatus.READ,
    )


def _payload() -> dict[str, object]:
    academic_text = "Academic abstract evidence."
    official_text = "Official guidance evidence."
    academic = ResearchSourceDocument(
        document_id="document-academic",
        candidate=_candidate("source-academic", ResearchSourceType.ACADEMIC, 1),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=academic_text,
        word_count=len(academic_text.split()),
        character_count=len(academic_text),
        reader="fixture-reader",
    )
    official = ResearchSourceDocument(
        document_id="document-official",
        candidate=_candidate(
            "source-official", ResearchSourceType.OFFICIAL_DOCUMENTATION, 2
        ),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=official_text,
        word_count=len(official_text.split()),
        character_count=len(official_text),
        reader="fixture-reader",
    )
    failed = ResearchSourceDocument(
        document_id="document-failed",
        candidate=_candidate("source-failed", ResearchSourceType.INDUSTRY, 3),
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        reader="fixture-reader",
        error=ResearchSourceDocumentError(
            error_type="ReadError", message="fixture failure", retryable=False
        ),
    )
    documents = ResearchSourceDocumentSet(
        request_id="request-1", documents=[academic, official, failed]
    )
    chunks = [
        DocumentChunk(
            document_id="document-official",
            chunk_id="chunk-official-0",
            ordinal=0,
            text=official_text,
            start_char=0,
            end_char=len(official_text),
        ),
        DocumentChunk(
            document_id="document-academic",
            chunk_id="chunk-academic-0",
            ordinal=0,
            text=academic_text,
            start_char=0,
            end_char=len(academic_text),
        ),
    ]
    provenance = [
        CrossSourceChunkProvenance(
            chunk_id="chunk-official-0",
            source_id="source-official",
            document_id="document-official",
            source_type=ResearchSourceType.OFFICIAL_DOCUMENTATION,
            start_character=0,
            end_character=len(official_text),
        ),
        CrossSourceChunkProvenance(
            chunk_id="chunk-academic-0",
            source_id="source-academic",
            document_id="document-academic",
            source_type=ResearchSourceType.ACADEMIC,
            start_character=0,
            end_character=len(academic_text),
        ),
    ]
    return {
        "request_id": "request-1",
        "document_set": documents,
        "chunks": chunks,
        "provenance": provenance,
        "failed_document_ids": ["document-failed"],
    }


def test_accepts_multiple_source_types_and_preserves_exact_provenance() -> None:
    result = CrossSourceChunkIngestionResult(**_payload())

    assert [item.chunk_id for item in result.ordered_chunks()] == [
        "chunk-academic-0",
        "chunk-official-0",
    ]
    assert {item.source_type for item in result.provenance} == {
        ResearchSourceType.ACADEMIC,
        ResearchSourceType.OFFICIAL_DOCUMENTATION,
    }
    assert result.failed_document_ids == ["document-failed"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_id", "wrong-source", "source_id must match"),
        ("document_id", "document-academic", "document_id must match"),
        ("source_type", ResearchSourceType.NEWS, "source_type must match"),
        ("end_character", 3, "range must match"),
    ],
)
def test_rejects_corrupted_provenance(field: str, value: object, message: str) -> None:
    payload = _payload()
    provenance = list(payload["provenance"])
    data = provenance[0].model_dump()
    data[field] = value
    provenance[0] = CrossSourceChunkProvenance(**data)
    payload["provenance"] = provenance

    with pytest.raises(ValidationError, match=message):
        CrossSourceChunkIngestionResult(**payload)


def test_rejects_chunk_text_not_matching_document_range() -> None:
    payload = _payload()
    chunks = list(payload["chunks"])
    data = chunks[0].model_dump()
    data["text"] = "X" * len(data["text"])
    chunks[0] = DocumentChunk(**data)
    payload["chunks"] = chunks

    with pytest.raises(ValidationError, match="exact document character range"):
        CrossSourceChunkIngestionResult(**payload)


def test_rejects_missing_or_duplicate_chunk_provenance() -> None:
    missing = _payload()
    missing["provenance"] = list(missing["provenance"])[1:]
    with pytest.raises(ValidationError, match="exactly one provenance"):
        CrossSourceChunkIngestionResult(**missing)

    duplicate = _payload()
    provenance = list(duplicate["provenance"])
    provenance.append(deepcopy(provenance[0]))
    duplicate["provenance"] = provenance
    with pytest.raises(ValidationError, match="provenance chunk IDs must be unique"):
        CrossSourceChunkIngestionResult(**duplicate)


def test_requires_exact_failed_document_accounting() -> None:
    payload = _payload()
    payload["failed_document_ids"] = []
    with pytest.raises(ValidationError, match="exactly identify failed documents"):
        CrossSourceChunkIngestionResult(**payload)


def test_requires_every_read_document_to_produce_a_chunk() -> None:
    payload = _payload()
    payload["chunks"] = list(payload["chunks"])[1:]
    payload["provenance"] = list(payload["provenance"])[1:]
    with pytest.raises(ValidationError, match="every read document"):
        CrossSourceChunkIngestionResult(**payload)


def test_rejects_noncontiguous_ordinals_per_document() -> None:
    payload = _payload()
    chunks = list(payload["chunks"])
    data = chunks[0].model_dump()
    data["ordinal"] = 1
    chunks[0] = DocumentChunk(**data)
    payload["chunks"] = chunks
    with pytest.raises(ValidationError, match="contiguous from zero"):
        CrossSourceChunkIngestionResult(**payload)


def test_rejects_unknown_fields() -> None:
    payload = _payload()
    payload["ranking_score"] = 0.9
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CrossSourceChunkIngestionResult(**payload)
