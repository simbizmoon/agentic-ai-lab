"""Schemas for deterministic RAG quality evaluation."""

from __future__ import annotations

import math

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RetrievalEvaluationCase(BaseModel):
    """One expected-document retrieval evaluation case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    case_id: str = Field(min_length=1)
    query: str
    expected_document_ids: list[str] = Field(min_length=1)
    top_k: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_case(self) -> RetrievalEvaluationCase:
        """Validate retrieval evaluation case consistency."""

        if not self.query.strip():
            raise ValueError(
                "retrieval evaluation query must not be blank"
            )

        if len(self.expected_document_ids) != len(
            set(self.expected_document_ids)
        ):
            raise ValueError(
                "expected document IDs must be unique"
            )

        if any(
            not document_id.strip()
            for document_id in self.expected_document_ids
        ):
            raise ValueError(
                "expected document IDs must not be blank"
            )

        return self


class RetrievalCaseEvaluation(BaseModel):
    """Evaluation result for one retrieval case."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    case_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    expected_document_ids: list[str] = Field(min_length=1)
    retrieved_document_ids: list[str] = Field(
        default_factory=list
    )
    matched_document_ids: list[str] = Field(
        default_factory=list
    )
    first_relevant_rank: int | None = Field(
        default=None,
        ge=1,
    )
    recall_at_k: float = Field(ge=0.0, le=1.0)
    reciprocal_rank: float = Field(ge=0.0, le=1.0)
    passed: bool

    @model_validator(mode="after")
    def validate_metrics(
        self,
    ) -> RetrievalCaseEvaluation:
        """Ensure retrieval metrics are finite."""

        if not math.isfinite(self.recall_at_k):
            raise ValueError(
                "recall_at_k must be finite"
            )

        if not math.isfinite(self.reciprocal_rank):
            raise ValueError(
                "reciprocal_rank must be finite"
            )

        if self.first_relevant_rank is None:
            if self.reciprocal_rank != 0.0:
                raise ValueError(
                    "reciprocal rank must be zero without a match"
                )
        elif self.reciprocal_rank != (
            1.0 / self.first_relevant_rank
        ):
            raise ValueError(
                "reciprocal rank must match first relevant rank"
            )

        return self


class RetrievalEvaluationSummary(BaseModel):
    """Aggregate metrics for multiple retrieval cases."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    cases: list[RetrievalCaseEvaluation] = Field(
        default_factory=list
    )
    case_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    pass_rate: float = Field(ge=0.0, le=1.0)
    mean_recall_at_k: float = Field(ge=0.0, le=1.0)
    mean_reciprocal_rank: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_summary(
        self,
    ) -> RetrievalEvaluationSummary:
        """Validate aggregate count consistency."""

        if self.case_count != len(self.cases):
            raise ValueError(
                "case_count must match cases length"
            )

        if self.passed_count != sum(
            case.passed for case in self.cases
        ):
            raise ValueError(
                "passed_count must match passed cases"
            )

        return self


class CitationEvaluationResult(BaseModel):
    """Deterministic evaluation of answer citation usage."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    expected_citation_ids: list[str] = Field(
        default_factory=list
    )
    cited_ids: list[str] = Field(default_factory=list)
    matched_ids: list[str] = Field(default_factory=list)
    missing_ids: list[str] = Field(default_factory=list)
    unexpected_ids: list[str] = Field(default_factory=list)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    passed: bool

    @model_validator(mode="after")
    def validate_citation_metrics(
        self,
    ) -> CitationEvaluationResult:
        """Ensure citation lists and metrics are consistent."""

        for values in (
            self.expected_citation_ids,
            self.cited_ids,
        ):
            if len(values) != len(set(values)):
                raise ValueError(
                    "citation IDs must be unique"
                )

        expected = set(self.expected_citation_ids)
        cited = set(self.cited_ids)

        if set(self.matched_ids) != expected & cited:
            raise ValueError(
                "matched citation IDs are inconsistent"
            )

        if set(self.missing_ids) != expected - cited:
            raise ValueError(
                "missing citation IDs are inconsistent"
            )

        if set(self.unexpected_ids) != cited - expected:
            raise ValueError(
                "unexpected citation IDs are inconsistent"
            )

        return self
