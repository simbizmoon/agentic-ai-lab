"""Offline integration tests for cross-source chunks and existing RAG components."""

from __future__ import annotations

import pytest

from app.rag.deterministic_embedding_provider import (
    DeterministicEmbeddingProvider,
)
from app.rag.document_embedder import embed_document_chunks
from app.rag.in_memory_vector_store import InMemoryVectorStore
from app.research.cross_source_chunk_ingestion_runtime import (
    CrossSourceChunkIngestionRuntime,
)
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
    *,
    source_id: str,
    source_type: ResearchSourceType,
    rank: int,
) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="stage6-step2-request",
        task_id=f"task-{rank}",
        query_id=f"query-{rank}",
        title=f"Source {rank}",
        url=f"https://example.com/source-{rank}",
        source_type=source_type,
        rank=rank,
        status=ResearchSourceCandidateStatus.READ,
    )


def _read_document(
    *,
    document_id: str,
    source_id: str,
    source_type: ResearchSourceType,
    rank: int,
    content: str,
) -> ResearchSourceDocument:
    return ResearchSourceDocument(
        document_id=document_id,
        candidate=_candidate(
            source_id=source_id,
            source_type=source_type,
            rank=rank,
        ),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="offline-integration-fixture",
    )


def _document_set() -> ResearchSourceDocumentSet:
    academic = _read_document(
        document_id="document-academic",
        source_id="source-academic",
        source_type=ResearchSourceType.ACADEMIC,
        rank=1,
        content=("Retrieval augmented generation combines retrieval with generation."),
    )
    official = _read_document(
        document_id="document-official",
        source_id="source-official",
        source_type=ResearchSourceType.OFFICIAL_DOCUMENTATION,
        rank=2,
        content="Official guidance requires citations to traceable source text.",
    )
    failed = ResearchSourceDocument(
        document_id="document-failed",
        candidate=_candidate(
            source_id="source-failed",
            source_type=ResearchSourceType.INDUSTRY,
            rank=3,
        ),
        status=ResearchSourceDocumentStatus.FAILED,
        content_type=ResearchSourceContentType.OTHER,
        reader="offline-integration-fixture",
        error=ResearchSourceDocumentError(
            error_type="FixtureReadError",
            message="The offline fixture intentionally failed.",
            retryable=False,
        ),
    )
    return ResearchSourceDocumentSet(
        request_id="stage6-step2-request",
        documents=[academic, official, failed],
    )


def test_cross_source_chunks_flow_through_embedding_and_vector_search() -> None:
    document_set = _document_set()
    ingestion = CrossSourceChunkIngestionRuntime(
        chunk_size=200,
        chunk_overlap=20,
    ).ingest(document_set=document_set)
    provider = DeterministicEmbeddingProvider(
        dimensions=16,
        model_name="stage6-offline-deterministic",
    )
    embedded = embed_document_chunks(
        chunks=ingestion.ordered_chunks(),
        provider=provider,
    )
    store = InMemoryVectorStore()
    store.add(embedded)

    academic_text = document_set.documents[0].content
    query_embedding = provider.embed_text(academic_text)
    results = store.search(query_embedding=query_embedding, top_k=2)

    assert store.count() == 2
    assert len(results) == 2
    assert results[0].score == pytest.approx(1.0)
    assert results[0].chunk.document_id == "document-academic"
    assert results[0].chunk.text == academic_text
    assert results[0].chunk.metadata == {
        "request_id": "stage6-step2-request",
        "task_id": "task-1",
        "source_id": "source-academic",
        "source_type": "academic",
    }

    provenance = {item.chunk_id: item for item in ingestion.provenance}[
        results[0].chunk.chunk_id
    ]
    assert provenance.source_id == "source-academic"
    assert provenance.document_id == "document-academic"
    assert provenance.source_type is ResearchSourceType.ACADEMIC
    assert (
        provenance.start_character,
        provenance.end_character,
    ) == (
        results[0].chunk.start_char,
        results[0].chunk.end_char,
    )
    assert (
        results[0].chunk.text
        == academic_text[provenance.start_character : provenance.end_character]
    )
    assert ingestion.failed_document_ids == ["document-failed"]


def test_offline_integration_is_deterministic_across_complete_runs() -> None:
    document_set = _document_set()

    def run_once() -> list[tuple[str, float, dict[str, object]]]:
        ingestion = CrossSourceChunkIngestionRuntime(
            chunk_size=200,
            chunk_overlap=20,
        ).ingest(document_set=document_set)
        provider = DeterministicEmbeddingProvider(dimensions=16)
        embedded = embed_document_chunks(
            chunks=ingestion.ordered_chunks(),
            provider=provider,
        )
        store = InMemoryVectorStore()
        store.add(embedded)
        query = provider.embed_text(document_set.documents[1].content)
        return [
            (result.chunk.chunk_id, result.score, result.chunk.metadata)
            for result in store.search(query_embedding=query, top_k=2)
        ]

    assert run_once() == run_once()


def test_failed_only_input_does_not_reach_embedding_or_vector_storage() -> None:
    full_set = _document_set()
    failed_only = ResearchSourceDocumentSet(
        request_id=full_set.request_id,
        documents=[full_set.documents[2]],
    )
    ingestion = CrossSourceChunkIngestionRuntime().ingest(document_set=failed_only)
    provider = DeterministicEmbeddingProvider(dimensions=8)
    embedded = embed_document_chunks(
        chunks=ingestion.chunks,
        provider=provider,
    )
    store = InMemoryVectorStore()
    store.add(embedded)

    assert ingestion.chunks == []
    assert ingestion.provenance == []
    assert ingestion.failed_document_ids == ["document-failed"]
    assert embedded == []
    assert store.count() == 0
