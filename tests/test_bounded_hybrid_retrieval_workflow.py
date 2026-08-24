"""Offline integration tests for bounded hybrid retrieval workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.rag.context_builder import build_rag_context
from app.rag.deterministic_embedding_provider import DeterministicEmbeddingProvider
from app.rag.document_embedder import embed_document_chunks
from app.research.bounded_hybrid_retrieval_workflow import (
    BoundedHybridRetrievalWorkflow,
)
from app.research.file_persistent_vector_index import FilePersistentVectorIndex
from app.research.persistent_vector_index_lifecycle import (
    PersistentVectorIndexLifecycle,
)
from app.research.persistent_vector_index_search_runtime import (
    PersistentVectorIndexSearchRuntime,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.hybrid_retrieval import HybridRetrievalRequest
from app.schemas.hybrid_retrieval_workflow import (
    HybridRetrievalWorkflowRequest,
    HybridRetrievalWorkflowResult,
)
from app.schemas.keyword_retrieval import KeywordRetrievalRequest

NOW = datetime(2026, 8, 24, 15, 0, tzinfo=UTC)
MODEL = "stage6-step5-deterministic"


def _chunk(chunk_id: str, text: str, source_type: str) -> DocumentChunk:
    return DocumentChunk(
        document_id=f"document-{chunk_id}",
        chunk_id=chunk_id,
        ordinal=0,
        text=text,
        start_char=0,
        end_char=len(text),
        metadata={
            "source_id": f"source-{chunk_id}",
            "source_type": source_type,
        },
    )


def _corpus() -> list[DocumentChunk]:
    return [
        _chunk(
            "academic-rag",
            "Retrieval augmented generation grounds answers in retrieved evidence.",
            "academic",
        ),
        _chunk(
            "patent-frame",
            "A patent apparatus includes a frame with stop members.",
            "primary_research",
        ),
        _chunk(
            "official-citation",
            "Official citation guidance requires exact source provenance.",
            "official_documentation",
        ),
    ]


def _setup(tmp_path: Path):
    chunks = _corpus()
    provider = DeterministicEmbeddingProvider(dimensions=16, model_name=MODEL)
    embedded = embed_document_chunks(chunks=chunks, provider=provider)
    directory = tmp_path / "index"
    PersistentVectorIndexLifecycle(
        store=FilePersistentVectorIndex(directory=directory),
        clock=lambda: NOW,
    ).create(
        index_id="stage6-step5-index",
        embedding_model=MODEL,
        embedding_dimensions=16,
        records=embedded,
    )
    workflow = BoundedHybridRetrievalWorkflow(
        semantic_retriever=PersistentVectorIndexSearchRuntime(
            store=FilePersistentVectorIndex(directory=directory)
        )
    )
    return chunks, provider, workflow


def _request(provider: DeterministicEmbeddingProvider, query: str, *, top_k: int = 2):
    return HybridRetrievalWorkflowRequest(
        keyword_request=KeywordRetrievalRequest(query=query, top_k=top_k),
        query_embedding=provider.embed_text(query),
        semantic_top_k=top_k,
        fusion_request=HybridRetrievalRequest(top_k=top_k),
    )


def test_workflow_runs_keyword_persistent_semantic_and_fusion(tmp_path: Path) -> None:
    chunks, provider, workflow = _setup(tmp_path)
    result = workflow.search(
        chunks=chunks,
        request=_request(provider, chunks[0].text),
    )
    assert result.keyword.matches
    assert result.semantic
    assert result.fusion.matches
    assert result.fusion.keyword_result_count == len(result.keyword.matches)
    assert result.fusion.semantic_result_count == len(result.semantic)
    assert result.fusion.matches[0].retrieval.chunk.chunk_id == "academic-rag"
    assert result.fusion.matches[0].matched_channel_count == 2


def test_workflow_preserves_channel_explanations_and_raw_scores(tmp_path: Path) -> None:
    chunks, provider, workflow = _setup(tmp_path)
    result = workflow.search(
        chunks=chunks,
        request=_request(provider, "patent frame stop members"),
    )
    keyword = result.keyword.matches[0]
    fused = next(
        item
        for item in result.fusion.matches
        if item.retrieval.chunk.chunk_id == keyword.retrieval.chunk.chunk_id
    )
    assert keyword.explanation.matched_terms == ["patent", "frame", "stop", "members"]
    assert fused.keyword_score == keyword.retrieval.score
    assert fused.semantic_score is not None
    assert fused.retrieval.chunk == keyword.retrieval.chunk


def test_workflow_output_feeds_existing_rag_context(tmp_path: Path) -> None:
    chunks, provider, workflow = _setup(tmp_path)
    result = workflow.search(
        chunks=chunks,
        request=_request(provider, "official citation guidance", top_k=1),
    )
    context = build_rag_context([item.retrieval for item in result.fusion.matches])
    assert "Official citation guidance" in context.context_text
    assert context.citations[0].chunk_id == "official-citation"
    assert context.citations[0].document_id == "document-official-citation"


def test_workflow_is_deterministic_across_restart(tmp_path: Path) -> None:
    chunks, provider, workflow = _setup(tmp_path)
    request = _request(provider, "retrieval evidence")
    first = workflow.search(chunks=chunks, request=request)
    second = workflow.search(chunks=chunks, request=request)
    assert first == second


def test_keyword_only_match_remains_visible(tmp_path: Path) -> None:
    chunks, provider, workflow = _setup(tmp_path)
    request = HybridRetrievalWorkflowRequest(
        keyword_request=KeywordRetrievalRequest(
            query="apparatus frame stop members", top_k=3
        ),
        query_embedding=provider.embed_text(chunks[0].text),
        semantic_top_k=1,
        fusion_request=HybridRetrievalRequest(top_k=1),
    )
    result = workflow.search(chunks=chunks, request=request)
    assert result.keyword.matches[0].retrieval.chunk.chunk_id == "patent-frame"
    assert result.semantic[0].chunk.chunk_id == "academic-rag"
    assert result.fusion.unique_chunk_count == 2


def test_request_requires_each_candidate_pool_to_cover_fusion_top_k(
    tmp_path: Path,
) -> None:
    _, provider, _ = _setup(tmp_path)
    with pytest.raises(ValidationError, match="keyword top_k"):
        HybridRetrievalWorkflowRequest(
            keyword_request=KeywordRetrievalRequest(query="query", top_k=1),
            query_embedding=provider.embed_text("query"),
            semantic_top_k=2,
            fusion_request=HybridRetrievalRequest(top_k=2),
        )
    with pytest.raises(ValidationError, match="semantic_top_k"):
        HybridRetrievalWorkflowRequest(
            keyword_request=KeywordRetrievalRequest(query="query", top_k=2),
            query_embedding=provider.embed_text("query"),
            semantic_top_k=1,
            fusion_request=HybridRetrievalRequest(top_k=2),
        )


def test_workflow_request_type_is_checked_before_retrieval(tmp_path: Path) -> None:
    chunks, _, workflow = _setup(tmp_path)
    with pytest.raises(TypeError, match="HybridRetrievalWorkflowRequest"):
        workflow.search(chunks=chunks, request="invalid")  # type: ignore[arg-type]


def test_result_contract_rejects_fusion_count_drift(tmp_path: Path) -> None:
    chunks, provider, workflow = _setup(tmp_path)
    result = workflow.search(
        chunks=chunks,
        request=_request(provider, "retrieval evidence"),
    )
    data = result.model_dump()
    data["fusion"]["keyword_result_count"] += 1
    with pytest.raises(ValidationError, match="fusion keyword count"):
        HybridRetrievalWorkflowResult.model_validate(data)


def test_no_external_provider_is_used(tmp_path: Path) -> None:
    chunks, provider, workflow = _setup(tmp_path)
    result = workflow.search(
        chunks=chunks,
        request=_request(provider, "retrieval evidence"),
    )
    snapshot = workflow._semantic_retriever.snapshot()
    assert snapshot is not None
    assert snapshot.content.embedding_model == MODEL
    assert result.fusion.matches
