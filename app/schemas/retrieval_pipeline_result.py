"""Schemas for completed retrieval pipeline operations."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.rag_context import RagContext
from app.schemas.retrieval_result import RetrievalResult


class RetrievalPipelineResult(BaseModel):
    """Retrieval results together with formatted RAG context."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    query: str
    results: list[RetrievalResult] = Field(
        default_factory=list
    )
    context: RagContext

    @model_validator(mode="after")
    def validate_result_consistency(
        self,
    ) -> RetrievalPipelineResult:
        """Ensure search results and context remain consistent."""

        if not self.query.strip():
            raise ValueError(
                "retrieval pipeline query must not be blank"
            )

        if len(self.context.citations) > len(self.results):
            raise ValueError(
                "context citations must not exceed retrieval results"
            )

        result_chunk_ids = {
            result.chunk.chunk_id
            for result in self.results
        }
        citation_chunk_ids = {
            citation.chunk_id
            for citation in self.context.citations
        }

        if not citation_chunk_ids.issubset(result_chunk_ids):
            raise ValueError(
                "context citations must reference retrieved Chunks"
            )

        return self
