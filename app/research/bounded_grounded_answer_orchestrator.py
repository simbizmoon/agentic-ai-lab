"""Bounded orchestration from packed evidence to a validated grounded answer."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from app.budget import (
    BudgetUsage,
    ExecutionBudget,
    ensure_within_budget,
    record_attempt,
)
from app.exceptions import ExecutionBudgetError
from app.rag.abstention_evaluator import is_abstention_answer
from app.rag.context_builder import build_rag_context
from app.rag.grounded_answer_service import GroundedAnswerServiceError
from app.research.bounded_answer_citation_verifier import BoundedAnswerCitationVerifier
from app.schemas.answer_citation_validation import (
    AnswerCitationValidationRequest,
    AnswerCitationValidationStatus,
)
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerGenerationUsage,
    GroundedAnswerWorkflowFailure,
    GroundedAnswerWorkflowFailureStage,
    GroundedAnswerWorkflowRequest,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.grounded_answer_result import GroundedAnswerResult
from app.schemas.rag_context import RagContext
from app.services.text_generation import TokenUsage


@dataclass(frozen=True)
class GroundedAnswerGenerationAttempt:
    answer: GroundedAnswerResult
    usage: TokenUsage | None
    elapsed_seconds: float

    def __post_init__(self) -> None:
        if self.elapsed_seconds < 0:
            raise ValueError("generation elapsed_seconds must not be negative")


class GroundedAnswerGeneratorProtocol(Protocol):
    def generate(
        self, *, question: str, context: RagContext
    ) -> GroundedAnswerGenerationAttempt: ...


class BoundedGroundedAnswerOrchestrator:
    """Generate once within budget and validate every answer citation."""

    def __init__(
        self,
        *,
        generator: GroundedAnswerGeneratorProtocol,
        citation_verifier: BoundedAnswerCitationVerifier,
    ) -> None:
        self._generator = generator
        self._citation_verifier = citation_verifier

    def run(
        self, *, request: GroundedAnswerWorkflowRequest
    ) -> BoundedGroundedAnswerWorkflowResult:
        if not isinstance(request, GroundedAnswerWorkflowRequest):
            raise TypeError("request must be a GroundedAnswerWorkflowRequest")
        retrievals = [item.retrieval for item in request.packing.included]
        context = build_rag_context(retrievals)
        budget = ExecutionBudget(
            max_attempts=request.generation_budget.maximum_attempts,
            max_recorded_tokens=request.generation_budget.maximum_recorded_tokens,
            max_elapsed_seconds=request.generation_budget.maximum_elapsed_seconds,
        )
        started = time.perf_counter()
        try:
            generated = self._generator.generate(
                question=request.question, context=context
            )
        except GroundedAnswerServiceError as exc:
            usage = record_attempt(
                usage=BudgetUsage(),
                recorded_tokens=0,
                elapsed_seconds=max(0.0, time.perf_counter() - started),
            )
            return self._generation_failed(
                request=request,
                usage=usage,
                code=exc.code,
                safe_message=exc.safe_message,
                retryable=exc.code == "model_request_failed",
            )
        except Exception:  # noqa: BLE001 - provider boundary must not leak details
            usage = record_attempt(
                usage=BudgetUsage(),
                recorded_tokens=0,
                elapsed_seconds=max(0.0, time.perf_counter() - started),
            )
            return self._generation_failed(
                request=request,
                usage=usage,
                code="generation_error",
                safe_message="Grounded answer generation failed.",
                retryable=False,
            )

        usage = record_attempt(
            usage=BudgetUsage(),
            recorded_tokens=generated.usage.total_tokens if generated.usage else 0,
            elapsed_seconds=generated.elapsed_seconds,
        )
        try:
            ensure_within_budget(budget=budget, usage=usage)
        except ExecutionBudgetError:
            return BoundedGroundedAnswerWorkflowResult(
                request=request,
                status=GroundedAnswerWorkflowStatus.INCOMPLETE,
                generation_usage=self._usage(usage),
                generation_budget_exhausted=True,
                answer=generated.answer,
                citation_validation=None,
                abstention_detected=False,
            )

        abstained = is_abstention_answer(answer_text=generated.answer.answer)
        try:
            validation = self._citation_verifier.verify(
                request=AnswerCitationValidationRequest(
                    question=request.question,
                    answer=generated.answer.answer,
                    context=context,
                    evidence_retrievals=retrievals,
                    citation_required=bool(retrievals),
                    budget=request.citation_validation_budget,
                    response_id=generated.answer.response_id,
                    model_name=generated.answer.model_name,
                )
            )
        except Exception:  # noqa: BLE001 - validation boundary returns safe failure
            return BoundedGroundedAnswerWorkflowResult(
                request=request,
                status=GroundedAnswerWorkflowStatus.VALIDATION_FAILED,
                generation_usage=self._usage(usage),
                generation_budget_exhausted=False,
                answer=generated.answer,
                citation_validation=None,
                abstention_detected=False,
                failure=GroundedAnswerWorkflowFailure(
                    stage=GroundedAnswerWorkflowFailureStage.VALIDATION,
                    code="citation_validation_error",
                    safe_message="Generated answer citation validation failed.",
                    retryable=False,
                ),
            )

        if validation.status is AnswerCitationValidationStatus.INCOMPLETE:
            status = GroundedAnswerWorkflowStatus.INCOMPLETE
            failure = None
            abstained = False
        elif validation.status is AnswerCitationValidationStatus.FAILED:
            status = GroundedAnswerWorkflowStatus.VALIDATION_FAILED
            failure = GroundedAnswerWorkflowFailure(
                stage=GroundedAnswerWorkflowFailureStage.VALIDATION,
                code="citation_validation_failed",
                safe_message="Generated answer citations were not supported.",
                retryable=False,
            )
            abstained = False
        else:
            status = (
                GroundedAnswerWorkflowStatus.ABSTAINED
                if abstained
                else GroundedAnswerWorkflowStatus.ANSWER_AVAILABLE
            )
            failure = None
        return BoundedGroundedAnswerWorkflowResult(
            request=request,
            status=status,
            generation_usage=self._usage(usage),
            generation_budget_exhausted=False,
            answer=generated.answer,
            citation_validation=validation,
            abstention_detected=abstained,
            failure=failure,
        )

    @staticmethod
    def _usage(usage: BudgetUsage) -> GroundedAnswerGenerationUsage:
        return GroundedAnswerGenerationUsage(
            attempts=usage.attempts,
            recorded_tokens=usage.recorded_tokens,
            elapsed_seconds=usage.elapsed_seconds,
        )

    @classmethod
    def _generation_failed(
        cls,
        *,
        request: GroundedAnswerWorkflowRequest,
        usage: BudgetUsage,
        code: str,
        safe_message: str,
        retryable: bool,
    ) -> BoundedGroundedAnswerWorkflowResult:
        return BoundedGroundedAnswerWorkflowResult(
            request=request,
            status=GroundedAnswerWorkflowStatus.GENERATION_FAILED,
            generation_usage=cls._usage(usage),
            generation_budget_exhausted=False,
            answer=None,
            citation_validation=None,
            abstention_detected=False,
            failure=GroundedAnswerWorkflowFailure(
                stage=GroundedAnswerWorkflowFailureStage.GENERATION,
                code=code,
                safe_message=safe_message,
                retryable=retryable,
            ),
        )
