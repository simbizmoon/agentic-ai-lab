"""Offline tests for conservative Stage 9 recorded-token costing."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from app.evals.stage9_approved_baseline_manifest_importer import (
    load_approved_baseline,
)
from app.evals.stage9_conservative_cost_estimator import (
    ConservativeStage9RecordedTokenCostEstimator,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopDecision,
    ResearchAgentLoopRound,
    ResearchAgentLoopUsage,
    ResearchAgentObservation,
    ResearchAgentObservationFailure,
    ResearchAgentObservationStatus,
    ResearchAgentRoundUsage,
    ResearchAgentTerminationReason,
)

MANIFEST = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "approved-live-baseline.json"
)
REVIEW = Path(
    "evals/manifests/stage9/stage9-single-agent-baseline-live-v1/"
    "runtime-budget-review.md"
)


def _result(recorded_tokens: int) -> BoundedResearchAgentLoopResult:
    request = BoundedResearchAgentLoopRequest(
        goal="Controlled Stage 9 costing test",
        constraints=["No external request"],
        allowed_tools=["bounded_grounded_answer"],
        budget=BoundedResearchAgentLoopBudget(
            maximum_rounds=1,
            maximum_tool_calls=1,
            maximum_provider_calls=1,
            maximum_recorded_tokens=max(recorded_tokens, 1),
            maximum_elapsed_seconds=10.0,
            maximum_external_requests=1,
        ),
    )
    observation = ResearchAgentObservation(
        observation_id="controlled-observation-001",
        tool_name="bounded_grounded_answer",
        status=ResearchAgentObservationStatus.TOOL_FAILED,
        failure=ResearchAgentObservationFailure(
            code="controlled_failure",
            safe_message="Controlled local result.",
            retryable=False,
        ),
    )
    round_usage = ResearchAgentRoundUsage(
        tool_calls=1,
        provider_calls=1,
        recorded_tokens=recorded_tokens,
        elapsed_seconds=0.1,
        external_requests=1,
    )
    round_item = ResearchAgentLoopRound(
        round_number=1,
        plan_id="controlled-plan-001",
        observations=[observation],
        decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
        rationale="Controlled local result.",
        usage=round_usage,
    )
    return BoundedResearchAgentLoopResult(
        request=request,
        rounds=[round_item],
        final_decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
        termination_reason=ResearchAgentTerminationReason.TERMINAL_FAILURE,
        usage=ResearchAgentLoopUsage(
            rounds=1,
            tool_calls=1,
            provider_calls=1,
            recorded_tokens=recorded_tokens,
            elapsed_seconds=0.1,
            external_requests=1,
        ),
        trace_id="controlled-trace-001",
    )


def test_uses_highest_locked_token_rate_as_upper_bound() -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    estimate = ConservativeStage9RecordedTokenCostEstimator().estimate(
        loop_result=_result(10_000),
        experiment=experiment,
    )

    assert estimate == Decimal("0.120000")


def test_zero_recorded_tokens_has_zero_estimated_cost() -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    estimate = ConservativeStage9RecordedTokenCostEstimator().estimate(
        loop_result=_result(0),
        experiment=experiment,
    )

    assert estimate == Decimal(0)


def test_case_and_phase_token_ceilings_have_conservative_cost_bounds() -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    estimator = ConservativeStage9RecordedTokenCostEstimator()

    assert estimator.estimate(
        loop_result=_result(30_000), experiment=experiment
    ) == Decimal("0.360000")
    assert estimator.estimate(
        loop_result=_result(120_000), experiment=experiment
    ) == Decimal("1.440000")


def test_estimate_remains_below_locked_development_monetary_ceiling() -> None:
    experiment = load_approved_baseline(MANIFEST, REVIEW)
    estimate = ConservativeStage9RecordedTokenCostEstimator().estimate(
        loop_result=_result(120_000), experiment=experiment
    )

    assert estimate < Decimal("1.50")
    assert experiment.plan.manifest.execution_budget.maximum_execution_cost == Decimal(
        "4.00"
    )
