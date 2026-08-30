"""Account for OpenAI planner calls inside Stage 9 research-loop usage."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopRound,
    ResearchAgentLoopUsage,
    ResearchAgentRoundUsage,
)
from app.services.text_generation import extract_token_usage, validate_token_usage


class ResponsesCreateProtocol(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class ResponsesClientProtocol(Protocol):
    responses: ResponsesCreateProtocol


@dataclass(frozen=True)
class Stage9PlannerUsageSnapshot:
    calls: int
    recorded_tokens: int
    elapsed_seconds: float


class Stage9PlannerUsageAccountingError(RuntimeError):
    """Planner usage was unavailable or violated the research-loop budget."""


class _MeteredResponsesResource:
    def __init__(self, *, delegate: ResponsesCreateProtocol) -> None:
        self._delegate = delegate
        self.calls = 0
        self.recorded_tokens = 0
        self.elapsed_seconds = 0.0

    def create(self, **kwargs: Any) -> Any:
        started = time.perf_counter()
        response = self._delegate.create(**kwargs)
        elapsed = max(0.0, time.perf_counter() - started)
        try:
            usage = extract_token_usage(response)
        except (AttributeError, TypeError, ValueError) as error:
            raise Stage9PlannerUsageAccountingError(
                "planner response did not expose valid token usage"
            ) from error
        if usage is None:
            raise Stage9PlannerUsageAccountingError(
                "planner response omitted token usage"
            )
        validate_token_usage(usage)
        self.calls += 1
        self.recorded_tokens += usage.total_tokens
        self.elapsed_seconds += elapsed
        return response


class Stage9MeteredPlannerClient:
    """OpenAI-compatible client proxy retaining only aggregate planner usage."""

    def __init__(self, *, client: ResponsesClientProtocol) -> None:
        self.responses = _MeteredResponsesResource(delegate=client.responses)

    def snapshot(self) -> Stage9PlannerUsageSnapshot:
        return Stage9PlannerUsageSnapshot(
            calls=self.responses.calls,
            recorded_tokens=self.responses.recorded_tokens,
            elapsed_seconds=self.responses.elapsed_seconds,
        )


class ResearchLoopProtocol(Protocol):
    def run(
        self, *, request: BoundedResearchAgentLoopRequest
    ) -> BoundedResearchAgentLoopResult: ...


class Stage9PlannerUsageAccountingLoop:
    """Merge planner calls, tokens, and latency into the first loop round."""

    def __init__(
        self,
        *,
        loop: ResearchLoopProtocol,
        meter: Stage9MeteredPlannerClient,
    ) -> None:
        self._loop = loop
        self._meter = meter

    def run(
        self, *, request: BoundedResearchAgentLoopRequest
    ) -> BoundedResearchAgentLoopResult:
        before = self._meter.snapshot()
        result = self._loop.run(request=request)
        after = self._meter.snapshot()
        delta = Stage9PlannerUsageSnapshot(
            calls=after.calls - before.calls,
            recorded_tokens=after.recorded_tokens - before.recorded_tokens,
            elapsed_seconds=after.elapsed_seconds - before.elapsed_seconds,
        )
        if delta.calls < 1:
            raise Stage9PlannerUsageAccountingError(
                "research loop did not execute the locked planner"
            )
        first = result.rounds[0]
        merged_usage = ResearchAgentRoundUsage(
            tool_calls=first.usage.tool_calls,
            provider_calls=first.usage.provider_calls + delta.calls,
            recorded_tokens=first.usage.recorded_tokens + delta.recorded_tokens,
            elapsed_seconds=first.usage.elapsed_seconds + delta.elapsed_seconds,
            external_requests=first.usage.external_requests + delta.calls,
        )
        rounds = [
            ResearchAgentLoopRound(
                round_number=first.round_number,
                plan_id=first.plan_id,
                observations=first.observations,
                decision=first.decision,
                rationale=first.rationale,
                usage=merged_usage,
            ),
            *result.rounds[1:],
        ]
        usage = ResearchAgentLoopUsage(
            rounds=len(rounds),
            tool_calls=sum(item.usage.tool_calls for item in rounds),
            provider_calls=sum(item.usage.provider_calls for item in rounds),
            recorded_tokens=sum(item.usage.recorded_tokens for item in rounds),
            elapsed_seconds=sum(item.usage.elapsed_seconds for item in rounds),
            external_requests=sum(item.usage.external_requests for item in rounds),
        )
        try:
            return BoundedResearchAgentLoopResult(
                request=result.request,
                rounds=rounds,
                final_decision=result.final_decision,
                termination_reason=result.termination_reason,
                usage=usage,
                trace_id=result.trace_id,
            )
        except ValueError as error:
            raise Stage9PlannerUsageAccountingError(
                "planner usage caused the research-loop budget to be exceeded"
            ) from error
