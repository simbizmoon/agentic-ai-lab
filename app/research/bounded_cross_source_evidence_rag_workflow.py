"""Compose hybrid retrieval, bounded reranking, and grounded RAG context."""

from __future__ import annotations

from collections.abc import Sequence

from app.rag.context_builder import build_rag_context
from app.research.bounded_cross_source_evidence_reranker import (
    BoundedCrossSourceEvidenceReranker,
)
from app.research.bounded_hybrid_retrieval_workflow import (
    BoundedHybridRetrievalWorkflow,
)
from app.schemas.cross_source_evidence_rag_workflow import (
    CrossSourceEvidenceRagWorkflowRequest,
    CrossSourceEvidenceRagWorkflowResult,
)
from app.schemas.document_chunk import DocumentChunk
from app.schemas.evidence_relevance_judgment import EvidenceRelevanceLevel
from app.schemas.retrieval_result import RetrievalResult


class BoundedCrossSourceEvidenceRagWorkflow:
    """Run exact hybrid retrieval, bounded relevance evaluation, and context build."""

    def __init__(
        self,
        *,
        retrieval_workflow: BoundedHybridRetrievalWorkflow,
        reranker: BoundedCrossSourceEvidenceReranker,
    ) -> None:
        self._retrieval_workflow = retrieval_workflow
        self._reranker = reranker

    def run(
        self,
        *,
        chunks: Sequence[DocumentChunk],
        request: CrossSourceEvidenceRagWorkflowRequest,
    ) -> CrossSourceEvidenceRagWorkflowResult:
        """Return relevant evaluated chunks and retain every audit record."""

        if not isinstance(request, CrossSourceEvidenceRagWorkflowRequest):
            raise TypeError("request must be a CrossSourceEvidenceRagWorkflowRequest")
        retrieval = self._retrieval_workflow.search(
            chunks=chunks,
            request=request.retrieval,
        )
        reranking = self._reranker.rerank(
            hybrid_response=retrieval.fusion,
            request=request.reranking,
        )
        selected = [
            item
            for item in reranking.items
            if item.judgment is not None
            and item.judgment.relevance_level
            in {
                EvidenceRelevanceLevel.DIRECTLY_RELEVANT,
                EvidenceRelevanceLevel.PARTIALLY_RELEVANT,
            }
        ]
        context_retrievals = [
            RetrievalResult(
                chunk=item.hybrid_match.retrieval.chunk,
                score=item.judgment.relevance_score,
                rank=rank,
            )
            for rank, item in enumerate(selected, start=1)
            if item.judgment is not None
        ]
        context = build_rag_context(context_retrievals)
        return CrossSourceEvidenceRagWorkflowResult(
            request=request,
            retrieval=retrieval,
            reranking=reranking,
            context_retrievals=context_retrievals,
            context=context,
            excluded_irrelevant_count=sum(
                item.judgment is not None
                and item.judgment.relevance_level is EvidenceRelevanceLevel.IRRELEVANT
                for item in reranking.items
            ),
            excluded_unevaluated_count=reranking.unevaluated_count,
        )
