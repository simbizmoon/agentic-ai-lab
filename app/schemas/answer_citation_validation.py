"""Contracts for bounded statement-to-evidence citation validation."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.rag_context import RagContext
from app.schemas.retrieval_result import RetrievalResult
from app.schemas.semantic_citation_judgment import (
    SemanticCitationJudgment,
    SemanticCitationSupportLevel,
)


class CitationPairEvaluationState(StrEnum):
    EVALUATED = "evaluated"
    UNEVALUATED = "unevaluated"


class AnswerCitationValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class AnswerCitationValidationBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    maximum_statements: int = Field(ge=1, le=200)
    maximum_pairs: int = Field(ge=1, le=500)
    maximum_attempts: int = Field(ge=1, le=500)
    maximum_recorded_tokens: int = Field(ge=1, le=1_000_000)
    maximum_elapsed_seconds: float = Field(gt=0.0, le=3600.0)

    @field_validator("maximum_elapsed_seconds", mode="before")
    @classmethod
    def validate_finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("maximum_elapsed_seconds must be finite")
        return value


class AnswerCitationValidationRequest(BaseModel):
    """Exact answer, rendered context, evidence retrievals, and limits."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    question: str
    answer: str
    context: RagContext
    evidence_retrievals: list[RetrievalResult] = Field(default_factory=list)
    citation_required: bool
    budget: AnswerCitationValidationBudget
    response_id: str | None = None
    model_name: str | None = None

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if not self.question.strip():
            raise ValueError("citation validation question must not be blank")
        if not self.answer.strip():
            raise ValueError("citation validation answer must not be blank")
        if self.citation_required != bool(self.context.citations):
            raise ValueError("citation_required must match context evidence")
        if len(self.context.citations) != len(self.evidence_retrievals):
            raise ValueError("every context citation requires one evidence retrieval")
        for citation, retrieval in zip(
            self.context.citations, self.evidence_retrievals, strict=True
        ):
            chunk = retrieval.chunk
            if (
                citation.document_id != chunk.document_id
                or citation.chunk_id != chunk.chunk_id
                or citation.rank != retrieval.rank
                or citation.score != retrieval.score
                or citation.start_char != chunk.start_char
                or citation.end_char != chunk.end_char
            ):
                raise ValueError("evidence retrieval must match exact context citation")
        if self.response_id is not None and not self.response_id.strip():
            raise ValueError("response_id must not be blank when provided")
        if self.model_name is not None and not self.model_name.strip():
            raise ValueError("model_name must not be blank when provided")
        return self


class AnswerStatement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    statement_id: str
    text: str
    start_character: int = Field(ge=0)
    end_character: int = Field(gt=0)
    cited_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_statement(self) -> Self:
        if not self.statement_id.strip() or not self.text.strip():
            raise ValueError("statement identity and text must not be blank")
        if self.end_character <= self.start_character:
            raise ValueError("statement character range is invalid")
        if any(not value.strip() for value in self.cited_ids):
            raise ValueError("statement cited_ids must not contain blanks")
        if len(self.cited_ids) != len(set(self.cited_ids)):
            raise ValueError("statement cited_ids must be unique")
        return self


class AnswerCitationPairValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    statement_id: str
    citation_id: str
    evidence: RetrievalResult
    evaluation_state: CitationPairEvaluationState
    judgment: SemanticCitationJudgment | None = None
    response_id: str | None = None
    request_id: str | None = None

    @model_validator(mode="after")
    def validate_pair(self) -> Self:
        if not self.statement_id.strip() or not self.citation_id.strip():
            raise ValueError("citation pair identities must not be blank")
        if self.evaluation_state is CitationPairEvaluationState.EVALUATED:
            if self.judgment is None or self.response_id is None:
                raise ValueError(
                    "evaluated citation pair requires judgment and response_id"
                )
            if not self.response_id.strip():
                raise ValueError("response_id must not be blank")
        elif any(
            value is not None
            for value in (self.judgment, self.response_id, self.request_id)
        ):
            raise ValueError(
                "unevaluated citation pair must not contain provider output"
            )
        return self


class AnswerCitationValidationUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    attempts: int = Field(ge=0)
    recorded_tokens: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0.0)
    statement_count: int = Field(ge=0)
    pair_count: int = Field(ge=0)
    evaluated_pair_count: int = Field(ge=0)
    unevaluated_pair_count: int = Field(ge=0)


class AnswerCitationValidationResult(BaseModel):
    """Complete statement and citation-pair classification for one answer."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: AnswerCitationValidationRequest
    statements: list[AnswerStatement] = Field(default_factory=list)
    pairs: list[AnswerCitationPairValidation] = Field(default_factory=list)
    uncited_statement_ids: list[str] = Field(default_factory=list)
    usage: AnswerCitationValidationUsage
    budget_exhausted: bool
    status: AnswerCitationValidationStatus

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if len(self.statements) > self.request.budget.maximum_statements:
            raise ValueError("statement count exceeds validation budget")
        statement_ids = [item.statement_id for item in self.statements]
        if len(statement_ids) != len(set(statement_ids)):
            raise ValueError("statement IDs must be unique")
        previous_end = 0
        available_ids = {item.citation_id for item in self.request.context.citations}
        expected_pairs: list[tuple[str, str]] = []
        for statement in self.statements:
            if statement.start_character < previous_end:
                raise ValueError("statement ranges must be ordered and nonoverlapping")
            if (
                self.request.answer[statement.start_character : statement.end_character]
                != statement.text
            ):
                raise ValueError("statement text must match exact answer range")
            if not set(statement.cited_ids).issubset(available_ids):
                raise ValueError("statement references an unknown citation")
            expected_pairs.extend(
                (statement.statement_id, citation_id)
                for citation_id in statement.cited_ids
            )
            previous_end = statement.end_character
        if len(expected_pairs) > self.request.budget.maximum_pairs:
            raise ValueError("citation pair count exceeds validation budget")

        actual_pairs = [(item.statement_id, item.citation_id) for item in self.pairs]
        if actual_pairs != expected_pairs:
            raise ValueError("citation pairs must exactly cover statement markers")
        evidence = {
            citation.citation_id: retrieval
            for citation, retrieval in zip(
                self.request.context.citations,
                self.request.evidence_retrievals,
                strict=True,
            )
        }
        for pair in self.pairs:
            if pair.evidence != evidence[pair.citation_id]:
                raise ValueError("citation pair must preserve exact evidence retrieval")

        expected_uncited = (
            [item.statement_id for item in self.statements if not item.cited_ids]
            if self.request.citation_required
            else []
        )
        if self.uncited_statement_ids != expected_uncited:
            raise ValueError("uncited statement IDs must match parsed statements")
        evaluated = sum(
            item.evaluation_state is CitationPairEvaluationState.EVALUATED
            for item in self.pairs
        )
        expected_usage = {
            "statement_count": len(self.statements),
            "pair_count": len(self.pairs),
            "evaluated_pair_count": evaluated,
            "unevaluated_pair_count": len(self.pairs) - evaluated,
        }
        for field_name, value in expected_usage.items():
            if getattr(self.usage, field_name) != value:
                raise ValueError("validation usage counts must match result items")
        budget = self.request.budget
        exceeded = (
            self.usage.attempts > budget.maximum_attempts
            or self.usage.recorded_tokens > budget.maximum_recorded_tokens
            or self.usage.elapsed_seconds > budget.maximum_elapsed_seconds
        )
        if exceeded and not self.budget_exhausted:
            raise ValueError("over-budget usage must mark budget_exhausted")
        if self.usage.unevaluated_pair_count and not self.budget_exhausted:
            raise ValueError("unevaluated pairs require budget_exhausted")

        rejected = any(
            pair.judgment is not None
            and pair.judgment.support_level
            in {
                SemanticCitationSupportLevel.UNSUPPORTED,
                SemanticCitationSupportLevel.CONTRADICTED,
            }
            for pair in self.pairs
        )
        expected_status = (
            AnswerCitationValidationStatus.INCOMPLETE
            if self.usage.unevaluated_pair_count
            else AnswerCitationValidationStatus.FAILED
            if self.uncited_statement_ids or rejected
            else AnswerCitationValidationStatus.PASSED
        )
        if self.status is not expected_status:
            raise ValueError("validation status must match statement and pair results")
        return self
