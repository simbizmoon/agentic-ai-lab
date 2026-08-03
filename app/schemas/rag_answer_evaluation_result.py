"""Schemas for end-to-end RAG answer evaluation results."""

from __future__ import annotations

import math

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.rag_evaluation import (
    CitationEvaluationResult,
)


class RagAnswerCaseEvaluation(BaseModel):
    """Evaluation result for one RAG question-answering case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_document_ids: list[str] = Field(min_length=1)
    retrieved_document_ids: list[str] = Field(
        default_factory=list
    )
    matched_document_ids: list[str] = Field(
        default_factory=list
    )
    expected_citation_ids: list[str] = Field(
        default_factory=list
    )
    cited_ids: list[str] = Field(default_factory=list)
    retrieval_passed: bool
    answer_generated: bool
    citation_evaluation: CitationEvaluationResult
    answer_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    passed: bool

    @model_validator(mode="after")
    def validate_case_result(
        self,
    ) -> RagAnswerCaseEvaluation:
        """Validate success and failure field consistency."""

        if self.answer_generated:
            if not self.answer_text:
                raise ValueError(
                    "generated answer requires answer_text"
                )

            if self.error_code is not None:
                raise ValueError(
                    "successful answer must not contain error_code"
                )

            if self.error_message is not None:
                raise ValueError(
                    "successful answer must not contain error_message"
                )
        else:
            if self.answer_text is not None:
                raise ValueError(
                    "failed answer must not contain answer_text"
                )

            if not self.error_code or not self.error_message:
                raise ValueError(
                    "failed answer requires error details"
                )

        expected_passed = (
            self.retrieval_passed
            and self.answer_generated
            and self.citation_evaluation.passed
        )

        if self.passed != expected_passed:
            raise ValueError(
                "case passed flag is inconsistent"
            )

        return self


class RagAnswerEvaluationSummary(BaseModel):
    """Aggregate metrics for end-to-end RAG evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    cases: list[RagAnswerCaseEvaluation] = Field(
        default_factory=list
    )
    case_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    retrieval_passed_count: int = Field(ge=0)
    answer_generated_count: int = Field(ge=0)
    citation_passed_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    retrieval_pass_rate: float = Field(ge=0.0, le=1.0)
    answer_generation_rate: float = Field(ge=0.0, le=1.0)
    citation_pass_rate: float = Field(ge=0.0, le=1.0)
    mean_citation_precision: float = Field(ge=0.0, le=1.0)
    mean_citation_recall: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_summary(
        self,
    ) -> RagAnswerEvaluationSummary:
        """Validate aggregate metrics and counts."""

        numeric_metrics = (
            self.pass_rate,
            self.retrieval_pass_rate,
            self.answer_generation_rate,
            self.citation_pass_rate,
            self.mean_citation_precision,
            self.mean_citation_recall,
        )

        if not all(
            math.isfinite(value)
            for value in numeric_metrics
        ):
            raise ValueError(
                "RAG answer evaluation metrics must be finite"
            )

        if self.case_count != len(self.cases):
            raise ValueError(
                "case_count must match cases length"
            )

        if self.passed_count != sum(
            case.passed
            for case in self.cases
        ):
            raise ValueError(
                "passed_count must match passed cases"
            )

        if self.retrieval_passed_count != sum(
            case.retrieval_passed
            for case in self.cases
        ):
            raise ValueError(
                "retrieval count must match cases"
            )

        if self.answer_generated_count != sum(
            case.answer_generated
            for case in self.cases
        ):
            raise ValueError(
                "answer count must match cases"
            )

        if self.citation_passed_count != sum(
            case.citation_evaluation.passed
            for case in self.cases
        ):
            raise ValueError(
                "citation count must match cases"
            )

        return self
