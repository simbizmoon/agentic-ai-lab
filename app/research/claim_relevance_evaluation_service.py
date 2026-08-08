"""Production orchestration for claim relevance evaluation."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from app.budget import (
    BudgetUsage,
    ExecutionBudget,
    ensure_can_start_attempt,
    record_attempt,
)
from app.exceptions import (
    ExecutionBudgetError,
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)
from app.research.openai_claim_relevance_evaluator import (
    ClaimRelevanceBatchEvaluationResult,
    ClaimRelevanceEvaluationResult,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceJudgment,
)
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_claim_relevance_evaluation import (
    ResearchClaimRelevanceEvaluation,
)
from app.schemas.research_request import ResearchRequest


class ClaimRelevanceEvaluatorProtocol(Protocol):
    """Evaluate semantic relevance for one research claim."""

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        claim_text: str,
    ) -> ClaimRelevanceEvaluationResult: ...


_BATCH_FALLBACK_ERRORS = (
    StructuredResponseIncompleteError,
    StructuredResponseParseError,
    StructuredResponseRefusalError,
    StructuredResponseStatusError,
    StructuredResponseValidationError,
)


class ClaimRelevanceEvaluationService:
    """Evaluate claims in stable order with an optional execution budget."""

    def __init__(
        self,
        *,
        evaluator: ClaimRelevanceEvaluatorProtocol,
        budget: ExecutionBudget | None = None,
        evaluation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._last_usage = BudgetUsage()
        self._last_api_usage = BudgetUsage()
        self._budget = budget
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (
                lambda: (
                    "claim-relevance-evaluation-"
                    f"{uuid4()}"
                )
            )
        )

    @property
    def last_usage(self) -> BudgetUsage:
        return self._last_usage

    @property
    def last_api_usage(self) -> BudgetUsage:
        """Return physical evaluator/API usage for observability."""

        return self._last_api_usage

    @property
    def budget(self) -> ExecutionBudget | None:
        """Return the configured evaluation budget."""

        return self._budget

    def evaluate(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> list[ResearchClaimRelevanceEvaluation]:
        """Evaluate claims while preserving code-owned identity."""

        if request.request_id != claim_set.request_id:
            raise ValueError(
                "request and claim_set request_id must match"
            )

        if not claim_set.claims:
            self._last_usage = BudgetUsage()
            self._last_api_usage = BudgetUsage()
            return []

        batch_evaluate = getattr(
            self._evaluator,
            "evaluate_batch",
            None,
        )
        if callable(batch_evaluate):
            return self._evaluate_batch_capable(
                request=request,
                claim_set=claim_set,
                batch_evaluate=batch_evaluate,
            )

        return self._evaluate_sequential(
            request=request,
            claim_set=claim_set,
        )

    def _evaluate_sequential(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> list[ResearchClaimRelevanceEvaluation]:
        """Preserve original single-item behavior."""

        usage = BudgetUsage()
        evaluations: list[
            ResearchClaimRelevanceEvaluation
        ] = []

        for claim in claim_set.claims:
            if self._budget is not None:
                try:
                    ensure_can_start_attempt(
                        budget=self._budget,
                        usage=usage,
                    )
                except ExecutionBudgetError:
                    break

            result = self._evaluator.evaluate(
                question=request.question,
                objective=request.objective,
                claim_text=claim.text,
            )
            evaluations.append(
                self._build_single_evaluation(
                    claim_id=claim.claim_id,
                    result=result,
                )
            )

            if self._budget is not None:
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=(
                        result.usage.total_tokens
                        if result.usage is not None
                        else 0
                    ),
                    elapsed_seconds=result.elapsed_seconds,
                )

        self._last_usage = usage
        self._last_api_usage = usage
        return evaluations

    def _evaluate_batch_capable(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
        batch_evaluate: Callable[
            ...,
            ClaimRelevanceBatchEvaluationResult,
        ],
    ) -> list[ResearchClaimRelevanceEvaluation]:
        """Batch eligible claims while preserving logical item limits."""

        eligible_claims = list(claim_set.claims)
        if self._budget is not None:
            eligible_claims = eligible_claims[
                : self._budget.max_attempts
            ]

        batch_items = [
            (f"item-{index:03d}", claim.text)
            for index, claim in enumerate(
                eligible_claims,
                start=1,
            )
        ]

        api_usage = BudgetUsage()
        batch_started = time.perf_counter()
        try:
            batch_result = batch_evaluate(
                question=request.question,
                objective=request.objective,
                claim_items=batch_items,
            )
        except _BATCH_FALLBACK_ERRORS:
            api_usage = record_attempt(
                usage=api_usage,
                recorded_tokens=0,
                elapsed_seconds=max(
                    0.0,
                    time.perf_counter() - batch_started,
                ),
            )
        else:
            batch_tokens = (
                batch_result.usage.total_tokens
                if batch_result.usage is not None
                else 0
            )
            api_usage = record_attempt(
                usage=api_usage,
                recorded_tokens=batch_tokens,
                elapsed_seconds=batch_result.elapsed_seconds,
            )
            evaluations = [
                self._build_batch_evaluation(
                    claim_id=claim.claim_id,
                    judgment=batch_result.judgments[item_id],
                    response_id=batch_result.response_id,
                    request_id=batch_result.request_id,
                    batch_tokens=batch_tokens,
                    batch_elapsed_seconds=(
                        batch_result.elapsed_seconds
                    ),
                    batch_item_count=len(eligible_claims),
                )
                for (item_id, _), claim in zip(
                    batch_items,
                    eligible_claims,
                    strict=True,
                )
            ]
            self._last_usage = BudgetUsage(
                attempts=len(evaluations),
                recorded_tokens=api_usage.recorded_tokens,
                elapsed_seconds=api_usage.elapsed_seconds,
            )
            self._last_api_usage = api_usage
            return evaluations

        evaluations: list[
            ResearchClaimRelevanceEvaluation
        ] = []
        logical_attempts = 0

        for claim in eligible_claims:
            if self._resource_budget_exhausted(api_usage):
                break

            result = self._evaluator.evaluate(
                question=request.question,
                objective=request.objective,
                claim_text=claim.text,
            )
            evaluations.append(
                self._build_single_evaluation(
                    claim_id=claim.claim_id,
                    result=result,
                )
            )
            logical_attempts += 1
            api_usage = record_attempt(
                usage=api_usage,
                recorded_tokens=(
                    result.usage.total_tokens
                    if result.usage is not None
                    else 0
                ),
                elapsed_seconds=result.elapsed_seconds,
            )

        self._last_usage = BudgetUsage(
            attempts=logical_attempts,
            recorded_tokens=api_usage.recorded_tokens,
            elapsed_seconds=api_usage.elapsed_seconds,
        )
        self._last_api_usage = api_usage
        return evaluations

    def _resource_budget_exhausted(
        self,
        usage: BudgetUsage,
    ) -> bool:
        """Check token/time gates without logical item cap."""

        if self._budget is None:
            return False
        return (
            usage.recorded_tokens
            >= self._budget.max_recorded_tokens
            or usage.elapsed_seconds
            >= self._budget.max_elapsed_seconds
        )

    def _build_single_evaluation(
        self,
        *,
        claim_id: str,
        result: ClaimRelevanceEvaluationResult,
    ) -> ResearchClaimRelevanceEvaluation:
        recorded_tokens = (
            result.usage.total_tokens
            if result.usage is not None
            else 0
        )
        return self._build_evaluation(
            claim_id=claim_id,
            judgment=result.judgment,
            response_id=result.response_id,
            request_id=result.request_id,
            metadata={
                "recorded_tokens": str(recorded_tokens),
                "elapsed_seconds": str(
                    result.elapsed_seconds
                ),
                "usage_scope": "single_item",
            },
        )

    def _build_batch_evaluation(
        self,
        *,
        claim_id: str,
        judgment: ClaimRelevanceJudgment,
        response_id: str,
        request_id: str | None,
        batch_tokens: int,
        batch_elapsed_seconds: float,
        batch_item_count: int,
    ) -> ResearchClaimRelevanceEvaluation:
        return self._build_evaluation(
            claim_id=claim_id,
            judgment=judgment,
            response_id=response_id,
            request_id=request_id,
            metadata={
                "recorded_tokens": str(batch_tokens),
                "elapsed_seconds": str(
                    batch_elapsed_seconds
                ),
                "usage_scope": "shared_batch",
                "batch_item_count": str(
                    batch_item_count
                ),
            },
        )

    def _build_evaluation(
        self,
        *,
        claim_id: str,
        judgment: ClaimRelevanceJudgment,
        response_id: str,
        request_id: str | None,
        metadata: dict[str, str],
    ) -> ResearchClaimRelevanceEvaluation:
        evaluation_id = (
            self._evaluation_id_factory().strip()
        )
        if not evaluation_id:
            raise ValueError(
                "evaluation_id factory returned blank value"
            )

        return ResearchClaimRelevanceEvaluation(
            evaluation_id=evaluation_id,
            claim_id=claim_id,
            relevance_level=judgment.relevance_level,
            relevance_score=judgment.relevance_score,
            rationale=judgment.rationale,
            issues=judgment.issues,
            metadata={
                "response_id": response_id,
                **(
                    {"request_id": request_id}
                    if request_id is not None
                    else {}
                ),
                **metadata,
            },
        )
