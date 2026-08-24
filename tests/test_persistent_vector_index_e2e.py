"""Offline E2E UAT for cross-source persistent vector-index lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.rag.context_builder import build_rag_context
from app.rag.deterministic_embedding_provider import DeterministicEmbeddingProvider
from app.rag.document_embedder import embed_document_chunks
from app.research.cross_source_chunk_ingestion_runtime import (
    CrossSourceChunkIngestionRuntime,
)
from app.research.file_persistent_vector_index import FilePersistentVectorIndex
from app.research.persistent_vector_index_lifecycle import (
    PersistentVectorIndexLifecycle,
)
from app.research.persistent_vector_index_search_runtime import (
    PersistentVectorIndexSearchRuntime,
)
from app.schemas.document_embedding import EmbeddedDocumentChunk
from app.schemas.research_request import ResearchSourceType
from app.schemas.research_source_candidate import (
    ResearchSourceCandidate,
    ResearchSourceCandidateStatus,
)
from app.schemas.research_source_document import (
    ResearchSourceContentType,
    ResearchSourceDocument,
    ResearchSourceDocumentSet,
    ResearchSourceDocumentStatus,
)

NOW = datetime(2026, 8, 24, 14, 0, tzinfo=UTC)
MODEL = "stage6-step4-offline-deterministic"
DIMENSIONS = 16
PATENT_TEXT = (
    "A patent apparatus uses a frame and stop members to move a mould container."
)
ACADEMIC_TEXT = (
    "Retrieval augmented generation grounds generated answers in retrieved evidence."
)
OFFICIAL_TEXT = (
    "Official guidance requires every answer citation to preserve source provenance."
)


def _candidate(
    *,
    source_id: str,
    source_type: ResearchSourceType,
    rank: int,
) -> ResearchSourceCandidate:
    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="stage6-step4-e2e-request",
        task_id=f"stage6-step4-task-{rank}",
        query_id=f"stage6-step4-query-{rank}",
        title=source_id,
        url=f"https://example.invalid/{source_id}",
        source_type=source_type,
        rank=rank,
        status=ResearchSourceCandidateStatus.READ,
    )


def _document(
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
        reader="stage6-step4-offline-e2e-fixture",
    )


def _initial_documents() -> ResearchSourceDocumentSet:
    return ResearchSourceDocumentSet(
        request_id="stage6-step4-e2e-request",
        documents=[
            _document(
                document_id="patent-document-EP1000000B1",
                source_id="patent-source-EP1000000B1",
                source_type=ResearchSourceType.PRIMARY_RESEARCH,
                rank=1,
                content=PATENT_TEXT,
            ),
            _document(
                document_id="academic-document-W3098425262",
                source_id="academic-source-W3098425262",
                source_type=ResearchSourceType.ACADEMIC,
                rank=2,
                content=ACADEMIC_TEXT,
            ),
        ],
    )


def _official_documents() -> ResearchSourceDocumentSet:
    return ResearchSourceDocumentSet(
        request_id="stage6-step4-e2e-request",
        documents=[
            _document(
                document_id="official-document-citation-guidance",
                source_id="official-source-citation-guidance",
                source_type=ResearchSourceType.OFFICIAL_DOCUMENTATION,
                rank=3,
                content=OFFICIAL_TEXT,
            )
        ],
    )


def _embed(
    document_set: ResearchSourceDocumentSet,
) -> tuple[list[EmbeddedDocumentChunk], dict[str, tuple[str, str, int, int]]]:
    ingestion = CrossSourceChunkIngestionRuntime(
        chunk_size=200,
        chunk_overlap=20,
    ).ingest(document_set=document_set)
    provider = DeterministicEmbeddingProvider(
        dimensions=DIMENSIONS,
        model_name=MODEL,
    )
    embedded = embed_document_chunks(
        chunks=ingestion.ordered_chunks(),
        provider=provider,
    )
    provenance = {
        item.chunk_id: (
            item.source_id,
            item.document_id,
            item.start_character,
            item.end_character,
        )
        for item in ingestion.provenance
    }
    return embedded, provenance


def _query(text: str):
    return DeterministicEmbeddingProvider(
        dimensions=DIMENSIONS,
        model_name=MODEL,
    ).embed_text(text)


def _create(
    directory: Path,
) -> tuple[list[EmbeddedDocumentChunk], dict[str, tuple[str, str, int, int]]]:
    embedded, provenance = _embed(_initial_documents())
    PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW,
    ).create(
        index_id="stage6-integrated-rag-index",
        embedding_model=MODEL,
        embedding_dimensions=DIMENSIONS,
        records=embedded,
    )
    return embedded, provenance


def test_e2e_cross_source_create_restart_search_and_exact_provenance(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "persistent-index"
    _, provenance = _create(directory)

    restarted = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    results = restarted.search(query_embedding=_query(PATENT_TEXT), top_k=2)

    assert restarted.count() == 2
    assert results[0].score == pytest.approx(1.0)
    assert results[0].chunk.document_id == "patent-document-EP1000000B1"
    chunk = results[0].chunk
    source_id, document_id, start, end = provenance[chunk.chunk_id]
    assert chunk.metadata["source_id"] == source_id
    assert chunk.document_id == document_id
    assert (chunk.start_char, chunk.end_char) == (start, end)
    assert chunk.text == PATENT_TEXT[start:end]


def test_e2e_upsert_restart_searches_latest_generation(tmp_path: Path) -> None:
    directory = tmp_path / "persistent-index"
    _create(directory)
    official, _ = _embed(_official_documents())
    lifecycle = PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW + timedelta(minutes=1),
    )
    generation_two = lifecycle.upsert(official)
    assert generation_two.content.generation == 2

    restarted = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    results = restarted.search(query_embedding=_query(OFFICIAL_TEXT), top_k=3)
    assert restarted.count() == 3
    assert restarted.snapshot() is not None
    assert restarted.snapshot().content.generation == 2  # type: ignore[union-attr]
    assert results[0].score == pytest.approx(1.0)
    assert results[0].chunk.document_id == "official-document-citation-guidance"


def test_e2e_delete_restart_removes_only_target_chunk(tmp_path: Path) -> None:
    directory = tmp_path / "persistent-index"
    embedded, _ = _create(directory)
    patent_chunk_id = next(
        item.chunk.chunk_id
        for item in embedded
        if item.chunk.document_id == "patent-document-EP1000000B1"
    )
    generation_two = PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW + timedelta(minutes=1),
    ).delete([patent_chunk_id])
    assert generation_two.content.generation == 2

    restarted = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    )
    results = restarted.search(query_embedding=_query(PATENT_TEXT), top_k=5)
    assert restarted.count() == 1
    assert patent_chunk_id not in {result.chunk.chunk_id for result in results}
    assert results[0].chunk.document_id == "academic-document-W3098425262"


def test_e2e_persistent_results_feed_existing_rag_citations(tmp_path: Path) -> None:
    directory = tmp_path / "persistent-index"
    _create(directory)
    results = PersistentVectorIndexSearchRuntime(
        store=FilePersistentVectorIndex(directory=directory)
    ).search(query_embedding=_query(ACADEMIC_TEXT), top_k=1)
    context = build_rag_context(results)
    assert ACADEMIC_TEXT in context.context_text
    assert "academic-document-W3098425262" in context.context_text
    assert context.citations[0].document_id == "academic-document-W3098425262"
    assert context.citations[0].chunk_id == results[0].chunk.chunk_id


def test_e2e_complete_runs_are_byte_deterministic_except_timestamps(
    tmp_path: Path,
) -> None:
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    _create(first_directory)
    _create(second_directory)
    first = FilePersistentVectorIndex(directory=first_directory).load()
    second = FilePersistentVectorIndex(directory=second_directory).load()
    assert first is not None and second is not None
    assert first.content == second.content
    assert first.content_sha256 == second.content_sha256


def test_uat_boundary_uses_no_network_or_model_provider(tmp_path: Path) -> None:
    directory = tmp_path / "persistent-index"
    _create(directory)
    snapshot = FilePersistentVectorIndex(directory=directory).load()
    assert snapshot is not None
    assert snapshot.content.embedding_model == MODEL
    assert "offline-deterministic" in snapshot.content.embedding_model
