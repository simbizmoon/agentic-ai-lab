"""Production orchestration for semantic answer coverage evaluation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import uuid4

from app.research.openai_answer_coverage_evaluator import (
    AnswerCoverageEvaluationResult,
)
from app.schemas.research_answer_coverage_evaluation import (
    ResearchAnswerCoverageEvaluation,
)
from app.schemas.research_claim import ResearchClaimSet
from app.schemas.research_request import ResearchRequest


class AnswerCoverageEvaluatorProtocol(Protocol):
    """Evaluate semantic answer coverage for one research claim set."""

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        claims: list[str],
    ) -> AnswerCoverageEvaluationResult: ...


class AnswerCoverageEvaluationService:
    """Evaluate one final claim set while preserving code-owned identity."""

    def __init__(
        self,
        *,
        evaluator: AnswerCoverageEvaluatorProtocol,
        evaluation_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._evaluation_id_factory = (
            evaluation_id_factory
            or (
                lambda: (
                    "answer-coverage-evaluation-"
                    f"{uuid4()}"
                )
            )
        )

    def evaluate(
        self,
        *,
        request: ResearchRequest,
        claim_set: ResearchClaimSet,
    ) -> ResearchAnswerCoverageEvaluation:
        """Evaluate the complete claim set against the research request."""

        if request.request_id != claim_set.request_id:
            raise ValueError(
                "request and claim_set request_id must match"
            )

        result = self._evaluator.evaluate(
            question=request.question,
            objective=request.objective,
            claims=[claim.text for claim in claim_set.claims],
        )

        evaluation_id = self._evaluation_id_factory().strip()
        if not evaluation_id:
            raise ValueError(
                "evaluation_id factory returned blank value"
            )

        recorded_tokens = (
            result.usage.total_tokens
            if result.usage is not None
            else 0
        )

        return ResearchAnswerCoverageEvaluation(
            evaluation_id=evaluation_id,
            request_id=request.request_id,
            claim_ids=[
                claim.claim_id
                for claim in claim_set.claims
            ],
            coverage_level=result.judgment.coverage_level,
            coverage_score=result.judgment.coverage_score,
            covered_aspects=result.judgment.covered_aspects,
            missing_aspects=result.judgment.missing_aspects,
            rationale=result.judgment.rationale,
            metadata={
                "response_id": result.response_id,
                **(
                    {"request_id": result.request_id}
                    if result.request_id is not None
                    else {}
                ),
                "recorded_tokens": str(recorded_tokens),
                "elapsed_seconds": str(
                    result.elapsed_seconds
                ),
            },
        )
