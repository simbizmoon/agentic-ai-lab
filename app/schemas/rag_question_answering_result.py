"""Schemas for completed RAG question-answering operations."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.grounded_answer_result import (
    GroundedAnswerResult,
)
from app.schemas.retrieval_pipeline_result import (
    RetrievalPipelineResult,
)


class RagQuestionAnsweringResult(BaseModel):
    """Retrieval and grounded answer results for one question."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    retrieval: RetrievalPipelineResult
    answer: GroundedAnswerResult

    @model_validator(mode="after")
    def validate_result_consistency(
        self,
    ) -> RagQuestionAnsweringResult:
        """Ensure retrieval and answer data describe one operation."""

        if self.retrieval.query != self.answer.question:
            raise ValueError(
                "retrieval query must match answer question"
            )

        retrieval_citation_ids = {
            citation.citation_id
            for citation in self.retrieval.context.citations
        }
        answer_citation_ids = {
            citation.citation_id
            for citation in self.answer.citations
        }

        if retrieval_citation_ids != answer_citation_ids:
            raise ValueError(
                "answer citations must match retrieval context citations"
            )

        if (
            self.answer.evidence_available
            != bool(self.retrieval.context.citations)
        ):
            raise ValueError(
                "answer evidence flag must match retrieval context"
            )

        return self
