"""Production orchestration for claim relevance evaluation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from app.budget import (
    BudgetUsage,
    ExecutionBudget,
    ensure_can_start_attempt,
    record_attempt,
)
from app.exceptions import ExecutionBudgetError
from app.research.openai_claim_relevance_evaluator import (
    ClaimRelevanceEvaluationResult,
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

            evaluation_id = (
                self._evaluation_id_factory().strip()
            )
            if not evaluation_id:
                raise ValueError(
                    "evaluation_id factory returned blank value"
                )

            recorded_tokens = (
                result.usage.total_tokens
                if result.usage is not None
                else 0
            )

            evaluations.append(
                ResearchClaimRelevanceEvaluation(
                    evaluation_id=evaluation_id,
                    claim_id=claim.claim_id,
                    relevance_level=(
                        result.judgment.relevance_level
                    ),
                    relevance_score=(
                        result.judgment.relevance_score
                    ),
                    rationale=result.judgment.rationale,
                    issues=result.judgment.issues,
                    metadata={
                        "response_id": result.response_id,
                        **(
                            {
                                "request_id": result.request_id,
                            }
                            if result.request_id is not None
                            else {}
                        ),
                        "recorded_tokens": str(
                            recorded_tokens
                        ),
                        "elapsed_seconds": str(
                            result.elapsed_seconds
                        ),
                    },
                )
            )

            if self._budget is not None:
                usage = record_attempt(
                    usage=usage,
                    recorded_tokens=recorded_tokens,
                    elapsed_seconds=result.elapsed_seconds,
                )

        self._last_usage = usage
        return evaluations
