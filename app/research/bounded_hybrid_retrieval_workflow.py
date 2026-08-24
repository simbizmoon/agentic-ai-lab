"""Bounded integration of keyword, persistent semantic, and RRF retrieval."""

from __future__ import annotations

from collections.abc import Sequence

from app.research.deterministic_hybrid_retriever import (
    DeterministicHybridRetriever,
)
from app.research.deterministic_keyword_retriever import (
    DeterministicKeywordRetriever,
)
from app.research.persistent_vector_index_search_runtime import (
    PersistentVectorIndexSearchRuntime,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.hybrid_retrieval_workflow import (
    HybridRetrievalWorkflowRequest,
    HybridRetrievalWorkflowResult,
)


class BoundedHybridRetrievalWorkflow:
    """Execute both retrieval channels and fuse their ranked outputs."""

    def __init__(
        self,
        *,
        semantic_retriever: PersistentVectorIndexSearchRuntime,
        keyword_retriever: DeterministicKeywordRetriever | None = None,
        fusion_retriever: DeterministicHybridRetriever | None = None,
    ) -> None:
        self._semantic_retriever = semantic_retriever
        self._keyword_retriever = keyword_retriever or DeterministicKeywordRetriever()
        self._fusion_retriever = fusion_retriever or DeterministicHybridRetriever()

    def search(
        self,
        *,
        chunks: Sequence[DocumentChunk],
        request: HybridRetrievalWorkflowRequest,
    ) -> HybridRetrievalWorkflowResult:
        """Run bounded channels and return their provenance-safe fusion."""

        if not isinstance(request, HybridRetrievalWorkflowRequest):
            raise TypeError("request must be a HybridRetrievalWorkflowRequest")
        keyword = self._keyword_retriever.search(
            chunks=chunks,
            request=request.keyword_request,
        )
        semantic = self._semantic_retriever.search(
            query_embedding=request.query_embedding,
            top_k=request.semantic_top_k,
        )
        fusion = self._fusion_retriever.fuse(
            keyword_results=[item.retrieval for item in keyword.matches],
            semantic_results=semantic,
            request=request.fusion_request,
        )
        return HybridRetrievalWorkflowResult(
            request=request,
            keyword=keyword,
            semantic=semantic,
            fusion=fusion,
        )
