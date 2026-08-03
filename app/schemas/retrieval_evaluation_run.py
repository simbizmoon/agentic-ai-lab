"""Schemas for retrieval evaluation runs."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.rag_evaluation import (
    RetrievalEvaluationSummary,
)


class RetrievalEvaluationRunResult(BaseModel):
    """Result of indexing and evaluating one retrieval dataset."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    dataset_id: str = Field(min_length=1)
    indexed_document_count: int = Field(ge=0)
    indexed_chunk_count: int = Field(ge=0)
    embedding_model: str = Field(min_length=1)
    embedding_dimensions: int = Field(gt=0)
    summary: RetrievalEvaluationSummary

    @model_validator(mode="after")
    def validate_run_result(
        self,
    ) -> RetrievalEvaluationRunResult:
        """Validate document and Chunk count consistency."""

        if (
            self.indexed_document_count == 0
            and self.indexed_chunk_count != 0
        ):
            raise ValueError(
                "indexed chunks require indexed documents"
            )

        return self
