"""Schemas for grounded document answers."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.rag_context import RagCitation


class GroundedAnswerResult(BaseModel):
    """A document-grounded answer with verified citations."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    question: str
    answer: str = Field(min_length=1)
    citations: list[RagCitation] = Field(default_factory=list)
    cited_ids: list[str] = Field(default_factory=list)
    response_id: str | None = None
    model_name: str = Field(min_length=1)
    evidence_available: bool

    @model_validator(mode="after")
    def validate_grounded_answer(
        self,
    ) -> GroundedAnswerResult:
        """Validate question, evidence, and citation consistency."""

        if not self.question.strip():
            raise ValueError(
                "grounded answer question must not be blank"
            )

        available_ids = {
            citation.citation_id
            for citation in self.citations
        }

        if len(self.cited_ids) != len(set(self.cited_ids)):
            raise ValueError(
                "cited IDs must be unique"
            )

        if not set(self.cited_ids).issubset(available_ids):
            raise ValueError(
                "cited IDs must reference available citations"
            )

        if self.evidence_available != bool(self.citations):
            raise ValueError(
                "evidence_available must match citation availability"
            )

        if not self.evidence_available and self.cited_ids:
            raise ValueError(
                "answer without evidence must not contain citations"
            )

        return self
