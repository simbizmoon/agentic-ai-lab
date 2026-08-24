"""Contracts for bounded keyword and persistent semantic retrieval fusion."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.document_embedding import TextEmbedding
from app.schemas.hybrid_retrieval import (
    HybridRetrievalRequest,
    HybridRetrievalResponse,
)
from app.schemas.keyword_retrieval import (
    KeywordRetrievalRequest,
    KeywordRetrievalResponse,
)
from app.schemas.retrieval_result import RetrievalResult


class HybridRetrievalWorkflowRequest(BaseModel):
    """Inputs and candidate budgets for one hybrid retrieval execution."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    keyword_request: KeywordRetrievalRequest
    query_embedding: TextEmbedding
    semantic_top_k: int = Field(default=5, ge=1, le=100)
    fusion_request: HybridRetrievalRequest = Field(
        default_factory=HybridRetrievalRequest
    )

    @model_validator(mode="after")
    def validate_candidate_budgets(self) -> Self:
        if self.keyword_request.top_k < self.fusion_request.top_k:
            raise ValueError("keyword top_k must cover fusion top_k")
        if self.semantic_top_k < self.fusion_request.top_k:
            raise ValueError("semantic_top_k must cover fusion top_k")
        return self


class HybridRetrievalWorkflowResult(BaseModel):
    """Auditable channel outputs and their validated fused result."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: HybridRetrievalWorkflowRequest
    keyword: KeywordRetrievalResponse
    semantic: list[RetrievalResult] = Field(default_factory=list)
    fusion: HybridRetrievalResponse

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.keyword.request != self.request.keyword_request:
            raise ValueError("keyword response must match workflow request")
        if len(self.semantic) > self.request.semantic_top_k:
            raise ValueError("semantic results must not exceed semantic_top_k")
        semantic_ranks = [item.rank for item in self.semantic]
        if semantic_ranks != list(range(1, len(self.semantic) + 1)):
            raise ValueError("semantic result ranks must be contiguous from one")
        semantic_ids = [item.chunk.chunk_id.casefold() for item in self.semantic]
        if len(set(semantic_ids)) != len(semantic_ids):
            raise ValueError("semantic result chunk IDs must be unique")
        if self.fusion.request != self.request.fusion_request:
            raise ValueError("fusion response must match workflow request")
        if self.fusion.keyword_result_count != len(self.keyword.matches):
            raise ValueError("fusion keyword count must match keyword response")
        if self.fusion.semantic_result_count != len(self.semantic):
            raise ValueError("fusion semantic count must match semantic response")

        union: dict[str, object] = {}
        for result in [
            *[item.retrieval for item in self.keyword.matches],
            *self.semantic,
        ]:
            identity = result.chunk.chunk_id.casefold()
            existing = union.get(identity)
            if existing is not None and existing != result.chunk:
                raise ValueError("workflow channels contain conflicting chunks")
            union[identity] = result.chunk
        if self.fusion.unique_chunk_count != len(union):
            raise ValueError("fusion unique count must match channel union")
        for match in self.fusion.matches:
            expected = union.get(match.retrieval.chunk.chunk_id.casefold())
            if expected != match.retrieval.chunk:
                raise ValueError("fused chunk must preserve an exact channel chunk")
        return self
