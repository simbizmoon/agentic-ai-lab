"""Contracts for hybrid retrieval, bounded reranking, and RAG context."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.cross_source_evidence_reranking import (
    CrossSourceEvidenceRerankingRequest,
    CrossSourceEvidenceRerankingResult,
)
from app.schemas.hybrid_retrieval_workflow import (
    HybridRetrievalWorkflowRequest,
    HybridRetrievalWorkflowResult,
)
from app.schemas.rag_context import RagContext
from app.schemas.retrieval_result import RetrievalResult


class CrossSourceEvidenceRagWorkflowRequest(BaseModel):
    """Bounded retrieval and reranking inputs for one context build."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    retrieval: HybridRetrievalWorkflowRequest
    reranking: CrossSourceEvidenceRerankingRequest

    @model_validator(mode="after")
    def validate_candidate_bounds(self) -> Self:
        if self.reranking.maximum_candidates < self.retrieval.fusion_request.top_k:
            raise ValueError("reranking maximum_candidates must cover fusion top_k")
        return self


class CrossSourceEvidenceRagWorkflowResult(BaseModel):
    """Auditable retrieval/reranking outputs and selected grounded context."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: CrossSourceEvidenceRagWorkflowRequest
    retrieval: HybridRetrievalWorkflowResult
    reranking: CrossSourceEvidenceRerankingResult
    context_retrievals: list[RetrievalResult] = Field(default_factory=list)
    context: RagContext
    excluded_irrelevant_count: int = Field(ge=0)
    excluded_unevaluated_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.retrieval.request != self.request.retrieval:
            raise ValueError("retrieval result must match workflow request")
        if self.reranking.request != self.request.reranking:
            raise ValueError("reranking result must match workflow request")
        if self.reranking.hybrid_response != self.retrieval.fusion:
            raise ValueError("reranking must consume the exact fused response")

        expected = [
            item
            for item in self.reranking.items
            if item.judgment is not None
            and item.judgment.relevance_level.value
            in {"directly_relevant", "partially_relevant"}
        ]
        if len(self.context_retrievals) != len(expected):
            raise ValueError("context retrievals must contain all relevant items")
        for rank, (retrieval, item) in enumerate(
            zip(self.context_retrievals, expected, strict=True), start=1
        ):
            if retrieval.rank != rank:
                raise ValueError("context retrieval ranks must be contiguous")
            if retrieval.chunk != item.hybrid_match.retrieval.chunk:
                raise ValueError("context retrieval must preserve the exact chunk")
            if retrieval.score != item.judgment.relevance_score:
                raise ValueError("context score must preserve relevance score")

        if len(self.context.citations) != len(self.context_retrievals):
            raise ValueError("context citations must match context retrievals")
        for citation, retrieval in zip(
            self.context.citations, self.context_retrievals, strict=True
        ):
            if (
                citation.document_id != retrieval.chunk.document_id
                or citation.chunk_id != retrieval.chunk.chunk_id
                or citation.rank != retrieval.rank
                or citation.score != retrieval.score
                or citation.start_char != retrieval.chunk.start_char
                or citation.end_char != retrieval.chunk.end_char
            ):
                raise ValueError("citation must preserve exact context provenance")

        irrelevant = sum(
            item.judgment is not None
            and item.judgment.relevance_level.value == "irrelevant"
            for item in self.reranking.items
        )
        if self.excluded_irrelevant_count != irrelevant:
            raise ValueError("excluded irrelevant count must match reranking")
        if self.excluded_unevaluated_count != self.reranking.unevaluated_count:
            raise ValueError("excluded unevaluated count must match reranking")
        return self
