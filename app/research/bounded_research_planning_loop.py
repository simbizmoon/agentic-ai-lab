"""Integrate the existing planning loop with bounded research decisions."""

from __future__ import annotations

from typing import Protocol

from app.research.bounded_grounded_answer_agent_tool import (
    BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
    GroundedAnswerToolObservationAdapter,
)
from app.research.deterministic_evidence_sufficiency_decider import (
    DeterministicEvidenceSufficiencyDecider,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopRequest,
    BoundedResearchAgentLoopResult,
    ResearchAgentLoopDecision,
    ResearchAgentLoopRound,
    ResearchAgentLoopUsage,
    ResearchAgentRoundUsage,
    ResearchAgentTerminationReason,
)
from app.schemas.planning_agent_loop import (
    PlanningAgentLoopRequest,
    PlanningAgentLoopResult,
)
from app.schemas.tool_execution import ToolExecutionResult, ToolExecutionStatus
from app.tracing.agent_trace_session import AgentTraceSession


class BoundedResearchPlanningLoopError(RuntimeError):
    """Raised when planning integration cannot preserve bounded contracts."""


class PlanningLoopProtocol(Protocol):
    def run(
        self,
        request: PlanningAgentLoopRequest,
        *,
        trace_session: AgentTraceSession | None = None,
    ) -> PlanningAgentLoopResult: ...


class ResearchPlanningRequestFactoryProtocol(Protocol):
    def create(
        self,
        *,
        round_number: int,
        research_request: BoundedResearchAgentLoopRequest,
        previous_rounds: list[ResearchAgentLoopRound],
    ) -> PlanningAgentLoopRequest: ...


class BoundedResearchPlanningLoop:
    """Run existing planning attempts under one evidence-aware loop budget."""

    def __init__(
        self,
        *,
        planning_loop: PlanningLoopProtocol,
        request_factory: ResearchPlanningRequestFactoryProtocol,
        observation_adapter: GroundedAnswerToolObservationAdapter | None = None,
        decider: DeterministicEvidenceSufficiencyDecider | None = None,
    ) -> None:
        self._planning_loop = planning_loop
        self._request_factory = request_factory
        self._observation_adapter = (
            observation_adapter or GroundedAnswerToolObservationAdapter()
        )
        self._decider = decider or DeterministicEvidenceSufficiencyDecider()

    def run(
        self,
        *,
        request: BoundedResearchAgentLoopRequest,
        trace_session: AgentTraceSession | None = None,
    ) -> BoundedResearchAgentLoopResult:
        if not isinstance(request, BoundedResearchAgentLoopRequest):
            raise TypeError("request must be a BoundedResearchAgentLoopRequest")
        rounds: list[ResearchAgentLoopRound] = []
        trace_id: str | None = None

        for round_number in range(1, request.budget.maximum_rounds + 1):
            planning_request = self._request_factory.create(
                round_number=round_number,
                research_request=request,
                previous_rounds=list(rounds),
            )
            if not isinstance(planning_request, PlanningAgentLoopRequest):
                raise BoundedResearchPlanningLoopError(
                    "request factory returned an invalid planning-loop request"
                )
            if planning_request.maximum_replans != 0:
                raise BoundedResearchPlanningLoopError(
                    "inner planning-loop replans must be zero"
                )
            try:
                planning_result = self._planning_loop.run(
                    planning_request, trace_session=trace_session
                )
            except Exception as exc:
                raise BoundedResearchPlanningLoopError(
                    "existing planning loop failed"
                ) from exc
            if not isinstance(planning_result, PlanningAgentLoopResult):
                raise BoundedResearchPlanningLoopError(
                    "planning loop returned an invalid result"
                )
            trace_id = planning_result.trace_id or trace_id
            plan_id = planning_result.attempts[-1].run.plan.plan_id
            tool_results = self._bounded_tool_results(planning_result)
            if not tool_results:
                tool_results = [self._missing_tool_result()]

            observations = []
            round_usages = []
            for position, tool_result in enumerate(tool_results, start=1):
                observation, usage = self._observation_adapter.adapt(
                    observation_id=(
                        f"round-{round_number:04d}-observation-{position:04d}"
                    ),
                    result=tool_result,
                )
                observations.append(observation)
                round_usages.append(usage)

            usage = self._sum_round_usage(round_usages)
            aggregate = self._aggregate_usage(rounds=rounds, current=usage)
            decision = self._decider.decide(
                observations=observations,
                usage_after_round=aggregate,
                budget=request.budget,
            )
            rounds.append(
                ResearchAgentLoopRound(
                    round_number=round_number,
                    plan_id=plan_id,
                    observations=observations,
                    decision=decision.decision,
                    rationale=decision.rationale,
                    usage=usage,
                )
            )
            if decision.decision is ResearchAgentLoopDecision.REPLAN:
                continue
            return BoundedResearchAgentLoopResult(
                request=request,
                rounds=rounds,
                final_decision=decision.decision,
                termination_reason=self._termination_reason(decision.decision),
                usage=aggregate,
                trace_id=trace_id,
            )

        raise BoundedResearchPlanningLoopError(
            "research loop ended without a terminal bounded decision"
        )

    @staticmethod
    def _bounded_tool_results(
        planning_result: PlanningAgentLoopResult,
    ) -> list[ToolExecutionResult]:
        return [
            step.tool_result
            for attempt in planning_result.attempts
            for cycle in attempt.run.cycles
            for step in cycle.step_results
            if step.tool_result is not None
            and step.tool_result.tool_name == BOUNDED_GROUNDED_ANSWER_TOOL_NAME
        ]

    @staticmethod
    def _missing_tool_result() -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
            status=ToolExecutionStatus.FAILED,
            error_message="The plan produced no grounded-answer tool observation.",
            metadata={
                "error_code": "grounded_tool_not_executed",
                "retryable": False,
            },
        )

    @staticmethod
    def _sum_round_usage(
        values: list[ResearchAgentRoundUsage],
    ) -> ResearchAgentRoundUsage:
        return ResearchAgentRoundUsage(
            tool_calls=sum(item.tool_calls for item in values),
            provider_calls=sum(item.provider_calls for item in values),
            recorded_tokens=sum(item.recorded_tokens for item in values),
            elapsed_seconds=sum(item.elapsed_seconds for item in values),
            external_requests=sum(item.external_requests for item in values),
        )

    @staticmethod
    def _aggregate_usage(
        *, rounds: list[ResearchAgentLoopRound], current: ResearchAgentRoundUsage
    ) -> ResearchAgentLoopUsage:
        usages = [item.usage for item in rounds] + [current]
        return ResearchAgentLoopUsage(
            rounds=len(usages),
            tool_calls=sum(item.tool_calls for item in usages),
            provider_calls=sum(item.provider_calls for item in usages),
            recorded_tokens=sum(item.recorded_tokens for item in usages),
            elapsed_seconds=sum(item.elapsed_seconds for item in usages),
            external_requests=sum(item.external_requests for item in usages),
        )

    @staticmethod
    def _termination_reason(
        decision: ResearchAgentLoopDecision,
    ) -> ResearchAgentTerminationReason:
        mapping = {
            ResearchAgentLoopDecision.GOAL_ACHIEVED: ResearchAgentTerminationReason.GOAL_ACHIEVED,
            ResearchAgentLoopDecision.ABSTAIN: ResearchAgentTerminationReason.ABSTAINED,
            ResearchAgentLoopDecision.HUMAN_REVIEW: ResearchAgentTerminationReason.HUMAN_REVIEW_REQUIRED,
            ResearchAgentLoopDecision.TERMINAL_FAILURE: ResearchAgentTerminationReason.TERMINAL_FAILURE,
            ResearchAgentLoopDecision.BUDGET_EXHAUSTED: ResearchAgentTerminationReason.BUDGET_EXHAUSTED,
        }
        try:
            return mapping[decision]
        except KeyError as exc:
            raise BoundedResearchPlanningLoopError(
                "nonterminal research decision cannot finish the loop"
            ) from exc
