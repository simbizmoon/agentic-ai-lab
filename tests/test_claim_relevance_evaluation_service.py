"""Tests for production claim relevance evaluation service."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from app.budget import ExecutionBudget
from app.research.claim_relevance_evaluation_service import (
    ClaimRelevanceEvaluationService,
)
from app.research.openai_claim_relevance_evaluator import (
    ClaimRelevanceEvaluationResult,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceJudgment,
    ClaimRelevanceLevel,
)
from app.schemas.research_claim import (
    ResearchClaim,
    ResearchClaimSet,
)
from app.schemas.research_request import (
    ResearchDepth,
    ResearchOutputFormat,
    ResearchRequest,
)
from app.services.text_generation import TokenUsage


def request(
    *,
    request_id: str = "request-1",
) -> ResearchRequest:
    return ResearchRequest(
        request_id=request_id,
        question="How can an agent bound model usage?",
        objective=(
            "Describe a concrete runtime mechanism "
            "that limits model calls."
        ),
        depth=ResearchDepth.QUICK,
        output_format=ResearchOutputFormat.BRIEF,
    )


def claim_set(
    *,
    request_id: str = "request-1",
    claim_count: int = 3,
) -> ResearchClaimSet:
    claims = [
        ResearchClaim.model_construct(
            claim_id=f"claim-{index}",
            text=f"Claim text {index}.",
        )
        for index in range(1, claim_count + 1)
    ]
    return ResearchClaimSet.model_construct(
        request_id=request_id,
        claims=claims,
    )


def result(
    *,
    level: ClaimRelevanceLevel = (
        ClaimRelevanceLevel.PARTIALLY_RELEVANT
    ),
    score: float = 0.5,
    total_tokens: int = 10,
    elapsed_seconds: float = 0.25,
    response_id: str = "resp-1",
    request_id: str | None = "req-openai-1",
) -> ClaimRelevanceEvaluationResult:
    return ClaimRelevanceEvaluationResult(
        judgment=ClaimRelevanceJudgment(
            relevance_level=level,
            relevance_score=score,
            rationale="Materially useful but incomplete.",
            issues=["Does not provide the full mechanism."],
        ),
        response_id=response_id,
        request_id=request_id,
        usage=TokenUsage(
            input_tokens=total_tokens,
            cached_input_tokens=0,
            output_tokens=0,
            reasoning_tokens=0,
            total_tokens=total_tokens,
        ),
        elapsed_seconds=elapsed_seconds,
    )


class FakeEvaluator:
    def __init__(
        self,
        results: Iterable[
            ClaimRelevanceEvaluationResult
        ],
    ) -> None:
        self._results = iter(results)
        self.calls: list[
            tuple[str, str, str]
        ] = []

    def evaluate(
        self,
        *,
        question: str,
        objective: str,
        claim_text: str,
    ) -> ClaimRelevanceEvaluationResult:
        self.calls.append(
            (question, objective, claim_text)
        )
        return next(self._results)


def id_factory(
    values: Iterable[str],
):
    iterator = iter(values)
    return lambda: next(iterator)


def test_service_evaluates_claims_in_stable_order_and_owns_identity(
) -> None:
    evaluator = FakeEvaluator(
        [
            result(
                level=ClaimRelevanceLevel.DIRECTLY_RELEVANT,
                score=0.9,
                response_id="resp-1",
            ),
            result(
                level=ClaimRelevanceLevel.PARTIALLY_RELEVANT,
                score=0.5,
                response_id="resp-2",
            ),
            result(
                level=ClaimRelevanceLevel.IRRELEVANT,
                score=0.1,
                response_id="resp-3",
            ),
        ]
    )
    service = ClaimRelevanceEvaluationService(
        evaluator=evaluator,
        evaluation_id_factory=id_factory(
            ["eval-1", "eval-2", "eval-3"]
        ),
    )

    values = service.evaluate(
        request=request(),
        claim_set=claim_set(),
    )

    assert [
        value.evaluation_id
        for value in values
    ] == ["eval-1", "eval-2", "eval-3"]
    assert [
        value.claim_id
        for value in values
    ] == ["claim-1", "claim-2", "claim-3"]
    assert [
        call[2]
        for call in evaluator.calls
    ] == [
        "Claim text 1.",
        "Claim text 2.",
        "Claim text 3.",
    ]
    assert (
        values[0].relevance_level
        is ClaimRelevanceLevel.DIRECTLY_RELEVANT
    )
    assert values[0].metadata["response_id"] == "resp-1"


def test_service_passes_only_question_objective_and_claim_text(
) -> None:
    evaluator = FakeEvaluator([result()])
    service = ClaimRelevanceEvaluationService(
        evaluator=evaluator,
        evaluation_id_factory=lambda: "eval-1",
    )
    research_request = request()

    service.evaluate(
        request=research_request,
        claim_set=claim_set(claim_count=1),
    )

    assert evaluator.calls == [
        (
            research_request.question,
            research_request.objective,
            "Claim text 1.",
        )
    ]


def test_service_rejects_request_identity_mismatch(
) -> None:
    service = ClaimRelevanceEvaluationService(
        evaluator=FakeEvaluator([result()]),
    )

    with pytest.raises(
        ValueError,
        match="request_id must match",
    ):
        service.evaluate(
            request=request(request_id="request-1"),
            claim_set=claim_set(
                request_id="request-2",
                claim_count=1,
            ),
        )


def test_service_rejects_blank_generated_evaluation_id(
) -> None:
    service = ClaimRelevanceEvaluationService(
        evaluator=FakeEvaluator([result()]),
        evaluation_id_factory=lambda: "   ",
    )

    with pytest.raises(
        ValueError,
        match="evaluation_id factory returned blank",
    ):
        service.evaluate(
            request=request(),
            claim_set=claim_set(claim_count=1),
        )


def test_attempt_budget_stops_before_next_call(
) -> None:
    evaluator = FakeEvaluator(
        [result(), result(), result()]
    )
    service = ClaimRelevanceEvaluationService(
        evaluator=evaluator,
        budget=ExecutionBudget(
            max_attempts=2,
            max_recorded_tokens=10_000,
            max_elapsed_seconds=60.0,
        ),
        evaluation_id_factory=id_factory(
            ["eval-1", "eval-2"]
        ),
    )

    values = service.evaluate(
        request=request(),
        claim_set=claim_set(claim_count=3),
    )

    assert len(values) == 2
    assert len(evaluator.calls) == 2


def test_token_budget_keeps_successful_crossing_result_then_stops(
) -> None:
    evaluator = FakeEvaluator(
        [
            result(total_tokens=11),
            result(total_tokens=1),
        ]
    )
    service = ClaimRelevanceEvaluationService(
        evaluator=evaluator,
        budget=ExecutionBudget(
            max_attempts=8,
            max_recorded_tokens=10,
            max_elapsed_seconds=60.0,
        ),
        evaluation_id_factory=lambda: "eval-1",
    )

    values = service.evaluate(
        request=request(),
        claim_set=claim_set(claim_count=2),
    )

    assert len(values) == 1
    assert len(evaluator.calls) == 1
    assert values[0].metadata["recorded_tokens"] == "11"


def test_time_budget_keeps_successful_crossing_result_then_stops(
) -> None:
    evaluator = FakeEvaluator(
        [
            result(elapsed_seconds=1.1),
            result(elapsed_seconds=0.1),
        ]
    )
    service = ClaimRelevanceEvaluationService(
        evaluator=evaluator,
        budget=ExecutionBudget(
            max_attempts=8,
            max_recorded_tokens=10_000,
            max_elapsed_seconds=1.0,
        ),
        evaluation_id_factory=lambda: "eval-1",
    )

    values = service.evaluate(
        request=request(),
        claim_set=claim_set(claim_count=2),
    )

    assert len(values) == 1
    assert len(evaluator.calls) == 1
    assert values[0].metadata["elapsed_seconds"] == "1.1"


def test_missing_token_usage_records_zero_tokens(
) -> None:
    evaluator_result = result()
    evaluator_result = ClaimRelevanceEvaluationResult(
        judgment=evaluator_result.judgment,
        response_id=evaluator_result.response_id,
        request_id=None,
        usage=None,
        elapsed_seconds=0.2,
    )
    service = ClaimRelevanceEvaluationService(
        evaluator=FakeEvaluator(
            [evaluator_result]
        ),
        budget=ExecutionBudget(
            max_attempts=1,
            max_recorded_tokens=1,
            max_elapsed_seconds=1.0,
        ),
        evaluation_id_factory=lambda: "eval-1",
    )

    values = service.evaluate(
        request=request(),
        claim_set=claim_set(claim_count=1),
    )

    assert values[0].metadata["recorded_tokens"] == "0"
    assert "request_id" not in values[0].metadata


def test_empty_claim_set_returns_empty_evaluations(
) -> None:
    evaluator = FakeEvaluator([])
    service = ClaimRelevanceEvaluationService(
        evaluator=evaluator,
        budget=ExecutionBudget(
            max_attempts=1,
            max_recorded_tokens=1,
            max_elapsed_seconds=1.0,
        ),
    )

    values = service.evaluate(
        request=request(),
        claim_set=claim_set(claim_count=0),
    )

    assert values == []
    assert evaluator.calls == []
