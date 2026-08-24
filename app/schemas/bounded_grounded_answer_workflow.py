"""Contracts for one bounded grounded-answer generation and validation workflow."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.answer_citation_validation import (
    AnswerCitationValidationBudget,
    AnswerCitationValidationResult,
    AnswerCitationValidationStatus,
)
from app.schemas.grounded_answer_result import GroundedAnswerResult
from app.schemas.rag_context_packing import RagContextPackingResult


class GroundedAnswerWorkflowStatus(StrEnum):
    ANSWER_AVAILABLE = "answer_available"
    ABSTAINED = "abstained"
    GENERATION_FAILED = "generation_failed"
    VALIDATION_FAILED = "validation_failed"
    INCOMPLETE = "incomplete"


class GroundedAnswerWorkflowFailureStage(StrEnum):
    GENERATION = "generation"
    VALIDATION = "validation"


class GroundedAnswerGenerationBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    maximum_attempts: int = Field(ge=1, le=100)
    maximum_recorded_tokens: int = Field(ge=1, le=1_000_000)
    maximum_elapsed_seconds: float = Field(gt=0.0, le=3600.0)

    @field_validator("maximum_elapsed_seconds", mode="before")
    @classmethod
    def validate_finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("maximum_elapsed_seconds must be finite")
        return value


class GroundedAnswerWorkflowRequest(BaseModel):
    """Exact packed evidence and independent generation/validation limits."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    question: str
    packing: RagContextPackingResult
    generation_budget: GroundedAnswerGenerationBudget
    citation_validation_budget: AnswerCitationValidationBudget

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if not self.question.strip():
            raise ValueError("grounded answer workflow question must not be blank")
        if self.question != self.question.strip():
            raise ValueError("grounded answer workflow question must be normalized")
        return self


class GroundedAnswerGenerationUsage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    attempts: int = Field(ge=0)
    recorded_tokens: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0.0)

    @field_validator("elapsed_seconds", mode="before")
    @classmethod
    def validate_finite_elapsed(cls, value: object) -> object:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("elapsed_seconds must be finite")
        return value


class GroundedAnswerWorkflowFailure(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    stage: GroundedAnswerWorkflowFailureStage
    code: str = Field(min_length=1, max_length=200)
    safe_message: str = Field(min_length=1, max_length=2000)
    retryable: bool

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        for field_name in ("code", "safe_message"):
            value = getattr(self, field_name)
            if not value.strip() or value != value.strip():
                raise ValueError(f"{field_name} must be normalized and nonblank")
        return self


class BoundedGroundedAnswerWorkflowResult(BaseModel):
    """Auditable generation, abstention, and citation-validation outcome."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    request: GroundedAnswerWorkflowRequest
    status: GroundedAnswerWorkflowStatus
    generation_usage: GroundedAnswerGenerationUsage
    generation_budget_exhausted: bool
    answer: GroundedAnswerResult | None = None
    citation_validation: AnswerCitationValidationResult | None = None
    abstention_detected: bool
    failure: GroundedAnswerWorkflowFailure | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        budget = self.request.generation_budget
        generation_over_budget = (
            self.generation_usage.attempts > budget.maximum_attempts
            or self.generation_usage.recorded_tokens > budget.maximum_recorded_tokens
            or self.generation_usage.elapsed_seconds > budget.maximum_elapsed_seconds
        )
        if generation_over_budget and not self.generation_budget_exhausted:
            raise ValueError("over-budget generation usage must mark exhausted")

        if self.answer is not None:
            self._validate_answer()
        if self.citation_validation is not None:
            self._validate_citation_validation()

        if self.status is GroundedAnswerWorkflowStatus.GENERATION_FAILED:
            self._require_generation_failure()
        elif self.status is GroundedAnswerWorkflowStatus.VALIDATION_FAILED:
            self._require_validation_failure()
        elif self.status is GroundedAnswerWorkflowStatus.INCOMPLETE:
            self._require_incomplete()
        elif self.status is GroundedAnswerWorkflowStatus.ABSTAINED:
            self._require_completed(abstained=True)
        else:
            self._require_completed(abstained=False)
        return self

    def _included_retrievals(self):
        return [item.retrieval for item in self.request.packing.included]

    def _validate_answer(self) -> None:
        assert self.answer is not None
        if self.answer.question != self.request.question:
            raise ValueError("generated answer question must match workflow request")
        retrievals = self._included_retrievals()
        if self.answer.evidence_available != bool(retrievals):
            raise ValueError("answer evidence flag must match packed evidence")
        if len(self.answer.citations) != len(retrievals):
            raise ValueError("answer citations must exactly cover packed evidence")
        for citation, retrieval in zip(self.answer.citations, retrievals, strict=True):
            chunk = retrieval.chunk
            if (
                citation.document_id != chunk.document_id
                or citation.chunk_id != chunk.chunk_id
                or citation.rank != retrieval.rank
                or citation.score != retrieval.score
                or citation.start_char != chunk.start_char
                or citation.end_char != chunk.end_char
            ):
                raise ValueError("answer citation must preserve packed evidence")

    def _validate_citation_validation(self) -> None:
        assert self.citation_validation is not None
        if self.answer is None:
            raise ValueError("citation validation requires a generated answer")
        validation_request = self.citation_validation.request
        if validation_request.question != self.request.question:
            raise ValueError("citation validation question must match workflow request")
        if validation_request.answer != self.answer.answer:
            raise ValueError("citation validation answer must match generated answer")
        if validation_request.budget != self.request.citation_validation_budget:
            raise ValueError("citation validation budget must match workflow request")
        if validation_request.evidence_retrievals != self._included_retrievals():
            raise ValueError("citation validation must use exact packed evidence")
        if validation_request.response_id != self.answer.response_id:
            raise ValueError("citation validation response ID must match answer")
        if validation_request.model_name != self.answer.model_name:
            raise ValueError("citation validation model must match answer")

    def _require_generation_failure(self) -> None:
        if self.answer is not None or self.citation_validation is not None:
            raise ValueError("generation failure must not contain answer outputs")
        if self.abstention_detected:
            raise ValueError("generation failure cannot be an abstention")
        if (
            self.failure is None
            or self.failure.stage is not GroundedAnswerWorkflowFailureStage.GENERATION
        ):
            raise ValueError("generation failure requires generation error details")

    def _require_validation_failure(self) -> None:
        if self.answer is None or self.citation_validation is None:
            raise ValueError("validation failure requires answer and validation")
        if self.citation_validation.status is not AnswerCitationValidationStatus.FAILED:
            raise ValueError("validation failure requires failed citation validation")
        if self.abstention_detected or self.generation_budget_exhausted:
            raise ValueError("validation failure cannot be abstained or incomplete")
        if (
            self.failure is None
            or self.failure.stage is not GroundedAnswerWorkflowFailureStage.VALIDATION
        ):
            raise ValueError("validation failure requires validation error details")

    def _require_incomplete(self) -> None:
        if self.answer is None:
            raise ValueError("incomplete workflow requires generated answer")
        validation_incomplete = (
            self.citation_validation is not None
            and self.citation_validation.status
            is AnswerCitationValidationStatus.INCOMPLETE
        )
        if not (self.generation_budget_exhausted or validation_incomplete):
            raise ValueError("incomplete workflow requires an exhausted budget")
        if self.failure is not None or self.abstention_detected:
            raise ValueError("incomplete workflow cannot contain failure or abstention")
        if self.citation_validation is not None and not validation_incomplete:
            raise ValueError("incomplete workflow cannot contain completed validation")

    def _require_completed(self, *, abstained: bool) -> None:
        if self.answer is None or self.citation_validation is None:
            raise ValueError("completed workflow requires answer and validation")
        if self.citation_validation.status is not AnswerCitationValidationStatus.PASSED:
            raise ValueError("completed workflow requires passed citation validation")
        if self.generation_budget_exhausted or self.failure is not None:
            raise ValueError(
                "completed workflow cannot contain budget or failure state"
            )
        if self.abstention_detected is not abstained:
            raise ValueError("workflow status must match abstention detection")
