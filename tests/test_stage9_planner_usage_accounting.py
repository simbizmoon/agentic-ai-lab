"""Offline tests for exact Stage 9 planner usage accounting."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.research.stage9_planner_usage_accounting import (
    Stage9MeteredPlannerClient,
    Stage9PlannerUsageAccountingError,
    Stage9PlannerUsageAccountingLoop,
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


def _response(*, total_tokens: int = 12):
    return SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=7,
            input_tokens_details=SimpleNamespace(cached_tokens=2),
            output_tokens=total_tokens - 7,
            output_tokens_details=SimpleNamespace(reasoning_tokens=1),
            total_tokens=total_tokens,
        )
    )


class Responses:
    def __init__(self, response) -> None:
        self.response = response

    def create(self, **kwargs):
        del kwargs
        return self.response


def _request(*, maximum_provider_calls: int = 3):
    return BoundedResearchAgentLoopRequest(
        goal="Answer from locked evidence",
        allowed_tools=["bounded_grounded_answer"],
        budget=BoundedResearchAgentLoopBudget(
            maximum_rounds=1,
            maximum_tool_calls=1,
            maximum_provider_calls=maximum_provider_calls,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
            maximum_external_requests=maximum_provider_calls,
        ),
    )


def _result(request):
    observation = ResearchAgentObservation(
        observation_id="observation-001",
        tool_name="bounded_grounded_answer",
        status=ResearchAgentObservationStatus.TOOL_FAILED,
        failure=ResearchAgentObservationFailure(
            code="controlled_failure",
            safe_message="Controlled failure.",
            retryable=False,
        ),
    )
    usage = ResearchAgentRoundUsage(
        tool_calls=1,
        provider_calls=2,
        recorded_tokens=20,
        elapsed_seconds=0.1,
        external_requests=2,
    )
    round_item = ResearchAgentLoopRound(
        round_number=1,
        plan_id="plan-001",
        observations=[observation],
        decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
        rationale="Controlled terminal failure.",
        usage=usage,
    )
    return BoundedResearchAgentLoopResult(
        request=request,
        rounds=[round_item],
        final_decision=ResearchAgentLoopDecision.TERMINAL_FAILURE,
        termination_reason=ResearchAgentTerminationReason.TERMINAL_FAILURE,
        usage=ResearchAgentLoopUsage(
            rounds=1,
            tool_calls=1,
            provider_calls=2,
            recorded_tokens=20,
            elapsed_seconds=0.1,
            external_requests=2,
        ),
    )


class Loop:
    def __init__(self, *, meter, response) -> None:
        self.meter = meter
        self.response = response

    def run(self, *, request):
        self.meter.responses.create(model="controlled")
        return _result(request)


def test_adds_planner_call_and_reported_tokens_to_loop_usage() -> None:
    meter = Stage9MeteredPlannerClient(
        client=SimpleNamespace(responses=Responses(_response()))
    )
    request = _request()
    result = Stage9PlannerUsageAccountingLoop(
        loop=Loop(meter=meter, response=_response()), meter=meter
    ).run(request=request)

    assert result.usage.provider_calls == 3
    assert result.usage.external_requests == 3
    assert result.usage.recorded_tokens == 32
    assert result.rounds[0].usage.provider_calls == 3
    assert meter.snapshot().calls == 1


def test_missing_provider_usage_fails_instead_of_estimating_tokens() -> None:
    meter = Stage9MeteredPlannerClient(
        client=SimpleNamespace(responses=Responses(SimpleNamespace(usage=None)))
    )
    with pytest.raises(Stage9PlannerUsageAccountingError, match="omitted"):
        meter.responses.create(model="controlled")


def test_planner_call_that_exceeds_loop_budget_fails_safely() -> None:
    meter = Stage9MeteredPlannerClient(
        client=SimpleNamespace(responses=Responses(_response()))
    )
    request = _request(maximum_provider_calls=2)
    with pytest.raises(Stage9PlannerUsageAccountingError, match="budget"):
        Stage9PlannerUsageAccountingLoop(
            loop=Loop(meter=meter, response=_response()), meter=meter
        ).run(request=request)
