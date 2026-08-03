"""Schema for completed RAG abstention evaluation runs."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.schemas.rag_abstention_evaluation import (
    RagAbstentionEvaluationSummary,
)


class RagAbstentionEvaluationRunResult(BaseModel):
    """Result of one RAG abstention evaluation run."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    dataset_id: str = Field(min_length=1)
    indexed_document_count: int = Field(ge=0)
    indexed_chunk_count: int = Field(ge=0)
    embedding_model: str = Field(min_length=1)
    embedding_dimensions: int = Field(gt=0)
    answer_model: str = Field(min_length=1)
    summary: RagAbstentionEvaluationSummary
