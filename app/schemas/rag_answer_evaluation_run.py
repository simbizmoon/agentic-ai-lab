"""Schemas for completed end-to-end RAG evaluation runs."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.schemas.rag_answer_evaluation_result import (
    RagAnswerEvaluationSummary,
)


class RagAnswerEvaluationRunResult(BaseModel):
    """Result of one end-to-end RAG evaluation run."""

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
    summary: RagAnswerEvaluationSummary
