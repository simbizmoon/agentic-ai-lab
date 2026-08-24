"""Offline E2E UAT for cross-source deterministic hybrid retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.rag.context_builder import build_rag_context
from app.rag.deterministic_embedding_provider import DeterministicEmbeddingProvider
from app.rag.document_embedder import embed_document_chunks
from app.research.bounded_hybrid_retrieval_workflow import (
    BoundedHybridRetrievalWorkflow,
)
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
from app.schemas.hybrid_retrieval import HybridRetrievalRequest
from app.schemas.hybrid_retrieval_workflow import HybridRetrievalWorkflowRequest
from app.schemas.keyword_retrieval import KeywordRetrievalRequest
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

NOW = datetime(2026, 8, 24, 16, 0, tzinfo=UTC)
MODEL = "stage6-step5-e2e-deterministic"
PATENT_TEXT = (
    "A patent apparatus includes a frame with stop members for a mould container."
)
ACADEMIC_TEXT = (
    "Retrieval augmented generation grounds answers in retrieved academic evidence."
)
OFFICIAL_TEXT = "Official guidance requires citations with exact source provenance."


def _candidate(source_id: str, source_type: ResearchSourceType, rank: int):
    return ResearchSourceCandidate(
        source_id=source_id,
        request_id="stage6-step5-e2e-request",
        task_id=f"stage6-step5-task-{rank}",
        query_id=f"stage6-step5-query-{rank}",
        title=source_id,
        url=f"https://example.invalid/{source_id}",
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
):
    return ResearchSourceDocument(
        document_id=document_id,
        candidate=_candidate(source_id, source_type, rank),
        status=ResearchSourceDocumentStatus.READ,
        content_type=ResearchSourceContentType.TEXT,
        content=content,
        word_count=len(content.split()),
        character_count=len(content),
        reader="stage6-step5-offline-e2e",
    )


def _document_set() -> ResearchSourceDocumentSet:
    return ResearchSourceDocumentSet(
        request_id="stage6-step5-e2e-request",
        documents=[
            _read_document(
                "patent-document-EP1000000B1",
                "patent-source-EP1000000B1",
                ResearchSourceType.PRIMARY_RESEARCH,
                1,
                PATENT_TEXT,
            ),
            _read_document(
                "academic-document-W3098425262",
                "academic-source-W3098425262",
                ResearchSourceType.ACADEMIC,
                2,
                ACADEMIC_TEXT,
            ),
            _read_document(
                "official-document-grounding",
                "official-source-grounding",
                ResearchSourceType.OFFICIAL_DOCUMENTATION,
                3,
                OFFICIAL_TEXT,
            ),
            ResearchSourceDocument(
                document_id="failed-document",
                candidate=_candidate(
                    "failed-source",
                    ResearchSourceType.INDUSTRY,
                    4,
                ),
                status=ResearchSourceDocumentStatus.FAILED,
                content_type=ResearchSourceContentType.OTHER,
                reader="stage6-step5-offline-e2e",
                error=ResearchSourceDocumentError(
                    error_type="OfflineFixtureError",
                    message="Intentional failed source fixture.",
                    retryable=False,
                ),
            ),
        ],
    )


def _setup(tmp_path: Path):
    documents = _document_set()
    ingestion = CrossSourceChunkIngestionRuntime(
        chunk_size=200,
        chunk_overlap=20,
    ).ingest(document_set=documents)
    provider = DeterministicEmbeddingProvider(dimensions=16, model_name=MODEL)
    embedded = embed_document_chunks(
        chunks=ingestion.ordered_chunks(),
        provider=provider,
    )
    directory = tmp_path / "persistent-index"
    PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW,
    ).create(
        index_id="stage6-step5-cross-source-index",
        embedding_model=MODEL,
        embedding_dimensions=16,
        records=embedded,
    )
    restarted = BoundedHybridRetrievalWorkflow(
        semantic_retriever=PersistentVectorIndexSearchRuntime(
            store=FilePersistentVectorIndex(directory=directory)
        )
    )
    provenance = {item.chunk_id: item for item in ingestion.provenance}
    return ingestion, provider, restarted, provenance


def _request(
    provider: DeterministicEmbeddingProvider,
    *,
    keyword_query: str,
    semantic_query: str,
    top_k: int = 3,
):
    return HybridRetrievalWorkflowRequest(
        keyword_request=KeywordRetrievalRequest(
            query=keyword_query,
            top_k=top_k,
        ),
        query_embedding=provider.embed_text(semantic_query),
        semantic_top_k=top_k,
        fusion_request=HybridRetrievalRequest(top_k=top_k),
    )


def test_e2e_restart_hybrid_search_preserves_exact_cross_source_provenance(
    tmp_path: Path,
) -> None:
    ingestion, provider, workflow, provenance = _setup(tmp_path)
    result = workflow.search(
        chunks=ingestion.ordered_chunks(),
        request=_request(
            provider,
            keyword_query="patent frame stop members",
            semantic_query=PATENT_TEXT,
        ),
    )
    first = result.fusion.matches[0]
    chunk = first.retrieval.chunk
    trace = provenance[chunk.chunk_id]
    assert first.matched_channel_count == 2
    assert chunk.document_id == "patent-document-EP1000000B1"
    assert chunk.metadata["source_id"] == trace.source_id
    assert chunk.document_id == trace.document_id
    assert (chunk.start_char, chunk.end_char) == (
        trace.start_character,
        trace.end_character,
    )
    assert chunk.text == PATENT_TEXT[trace.start_character : trace.end_character]


def test_e2e_divergent_channels_preserve_both_candidate_origins(tmp_path: Path) -> None:
    ingestion, provider, workflow, _ = _setup(tmp_path)
    result = workflow.search(
        chunks=ingestion.ordered_chunks(),
        request=_request(
            provider,
            keyword_query="frame stop members",
            semantic_query=ACADEMIC_TEXT,
        ),
    )
    by_id = {item.retrieval.chunk.document_id: item for item in result.fusion.matches}
    assert "patent-document-EP1000000B1" in by_id
    assert "academic-document-W3098425262" in by_id
    assert by_id["patent-document-EP1000000B1"].keyword_rank == 1
    assert by_id["academic-document-W3098425262"].semantic_rank == 1


def test_e2e_failed_document_never_enters_any_retrieval_channel(tmp_path: Path) -> None:
    ingestion, provider, workflow, _ = _setup(tmp_path)
    result = workflow.search(
        chunks=ingestion.ordered_chunks(),
        request=_request(
            provider,
            keyword_query="retrieval evidence",
            semantic_query=ACADEMIC_TEXT,
        ),
    )
    assert ingestion.failed_document_ids == ["failed-document"]
    all_ids = {item.retrieval.chunk.document_id for item in result.fusion.matches}
    assert "failed-document" not in all_ids


def test_e2e_hybrid_results_feed_exact_rag_citations(tmp_path: Path) -> None:
    ingestion, provider, workflow, provenance = _setup(tmp_path)
    result = workflow.search(
        chunks=ingestion.ordered_chunks(),
        request=_request(
            provider,
            keyword_query="official citations source provenance",
            semantic_query=OFFICIAL_TEXT,
            top_k=1,
        ),
    )
    retrievals = [item.retrieval for item in result.fusion.matches]
    context = build_rag_context(retrievals)
    citation = context.citations[0]
    trace = provenance[citation.chunk_id]
    assert OFFICIAL_TEXT in context.context_text
    assert citation.document_id == trace.document_id
    assert (citation.start_char, citation.end_char) == (
        trace.start_character,
        trace.end_character,
    )


def test_e2e_fusion_explanation_has_no_quality_or_winner_judgment(
    tmp_path: Path,
) -> None:
    ingestion, provider, workflow, _ = _setup(tmp_path)
    result = workflow.search(
        chunks=ingestion.ordered_chunks(),
        request=_request(
            provider,
            keyword_query="retrieval evidence",
            semantic_query=ACADEMIC_TEXT,
        ),
    )
    serialized = result.model_dump(mode="json")
    forbidden = {
        "winner",
        "best_source",
        "source_authority",
        "paper_quality",
        "patent_validity",
        "legal_conclusion",
    }

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert forbidden.isdisjoint(keys(serialized))


def test_e2e_complete_hybrid_execution_is_deterministic(tmp_path: Path) -> None:
    ingestion, provider, workflow, _ = _setup(tmp_path)
    request = _request(
        provider,
        keyword_query="retrieval source evidence",
        semantic_query=ACADEMIC_TEXT,
    )
    first = workflow.search(chunks=ingestion.ordered_chunks(), request=request)
    second = workflow.search(chunks=ingestion.ordered_chunks(), request=request)
    assert first == second
    assert [item.fused_score for item in first.fusion.matches] == [
        item.retrieval.score for item in first.fusion.matches
    ]


def test_e2e_offline_boundary_is_explicit(tmp_path: Path) -> None:
    ingestion, _, workflow, _ = _setup(tmp_path)
    snapshot = workflow._semantic_retriever.snapshot()
    assert snapshot is not None
    assert snapshot.content.embedding_model == MODEL
    assert len(snapshot.content.records) == len(ingestion.chunks) == 3
    assert "deterministic" in snapshot.content.embedding_model
