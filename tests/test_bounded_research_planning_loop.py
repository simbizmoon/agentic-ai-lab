"""Offline tests for existing planning-loop research integration."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.rag.context_builder import build_rag_context
from app.research.bounded_answer_citation_verifier import BoundedAnswerCitationVerifier
from app.research.bounded_grounded_answer_agent_tool import (
    BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
)
from app.research.bounded_research_planning_loop import (
    BoundedResearchPlanningLoop,
    BoundedResearchPlanningLoopError,
)
from app.schemas.answer_citation_validation import (
    AnswerCitationValidationBudget,
    AnswerCitationValidationRequest,
)
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerGenerationBudget,
    GroundedAnswerGenerationUsage,
    GroundedAnswerWorkflowRequest,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    BoundedResearchAgentLoopRequest,
    ResearchAgentLoopDecision,
)
from app.schemas.grounded_answer_result import GroundedAnswerResult
from app.schemas.planning_agent_loop import (
    PlanningAgentLoopRequest,
    PlanningAgentLoopResult,
)
from app.schemas.rag_context_packing import (
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)
from app.schemas.tool_execution import ToolExecutionResult, ToolExecutionStatus


def _research_request(**budget_updates: object) -> BoundedResearchAgentLoopRequest:
    budget: dict[str, object] = {
        "maximum_rounds": 2,
        "maximum_tool_calls": 2,
        "maximum_provider_calls": 2,
        "maximum_recorded_tokens": 100,
        "maximum_elapsed_seconds": 10.0,
        "maximum_external_requests": 2,
    }
    budget.update(budget_updates)
    return BoundedResearchAgentLoopRequest(
        goal="Produce a bounded grounded answer",
        allowed_tools=[BOUNDED_GROUNDED_ANSWER_TOOL_NAME],
        budget=BoundedResearchAgentLoopBudget(**budget),
    )


def _planning_request(*, maximum_replans: int = 0) -> PlanningAgentLoopRequest:
    return PlanningAgentLoopRequest.model_construct(
        initial=SimpleNamespace(), maximum_replans=maximum_replans
    )


class RequestFactory:
    def __init__(self, *, maximum_replans: int = 0, invalid: bool = False) -> None:
        self.maximum_replans = maximum_replans
        self.invalid = invalid
        self.calls: list[tuple[int, int]] = []

    def create(
        self,
        *,
        round_number: int,
        research_request: BoundedResearchAgentLoopRequest,
        previous_rounds: list[object],
    ) -> object:
        del research_request
        self.calls.append((round_number, len(previous_rounds)))
        if self.invalid:
            return object()
        return _planning_request(maximum_replans=self.maximum_replans)


class Evaluator:
    def evaluate(self, **values: Any) -> object:
        raise AssertionError(f"empty evidence must not be evaluated: {values}")


def _workflow_request() -> GroundedAnswerWorkflowRequest:
    packing_request = RagContextPackingRequest(
        candidates=[],
        budget=RagContextPackingBudget(
            maximum_items=1,
            maximum_utf8_bytes=100,
            maximum_estimated_tokens=20,
            token_estimator_id="stage7-step5-offline-v1",
        ),
    )
    return GroundedAnswerWorkflowRequest(
        question="What is supported?",
        packing=RagContextPackingResult(
            request=packing_request,
            included=[],
            omitted=[],
            usage=RagContextPackingUsage(
                candidate_count=0,
                included_count=0,
                omitted_count=0,
                context_utf8_bytes=0,
                estimated_tokens=0,
            ),
            was_truncated=False,
        ),
        generation_budget=GroundedAnswerGenerationBudget(
            maximum_attempts=1,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
        ),
        citation_validation_budget=AnswerCitationValidationBudget(
            maximum_statements=5,
            maximum_pairs=5,
            maximum_attempts=5,
            maximum_recorded_tokens=100,
            maximum_elapsed_seconds=10.0,
        ),
    )


def _workflow(
    status: GroundedAnswerWorkflowStatus,
) -> BoundedGroundedAnswerWorkflowResult:
    request = _workflow_request()
    context = build_rag_context([])
    answer = GroundedAnswerResult(
        question=request.question,
        answer="The supplied evidence is insufficient.",
        citations=[],
        cited_ids=[],
        response_id="response-001",
        model_name="controlled-local-generator",
        evidence_available=False,
    )
    usage = GroundedAnswerGenerationUsage(
        attempts=1, recorded_tokens=5, elapsed_seconds=0.01
    )
    if status is GroundedAnswerWorkflowStatus.INCOMPLETE:
        return BoundedGroundedAnswerWorkflowResult(
            request=request,
            status=status,
            generation_usage=usage,
            generation_budget_exhausted=True,
            answer=answer,
            citation_validation=None,
            abstention_detected=False,
        )
    validation = BoundedAnswerCitationVerifier(evaluator=Evaluator()).verify(
        request=AnswerCitationValidationRequest(
            question=request.question,
            answer=answer.answer,
            context=context,
            evidence_retrievals=[],
            citation_required=False,
            budget=request.citation_validation_budget,
            response_id=answer.response_id,
            model_name=answer.model_name,
        )
    )
    return BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=status,
        generation_usage=usage,
        generation_budget_exhausted=False,
        answer=answer,
        citation_validation=validation,
        abstention_detected=True,
    )


def _success_result(
    status: GroundedAnswerWorkflowStatus,
    *,
    provider_calls: int = 1,
    plan_id: str = "plan-001",
    trace_id: str | None = "trace-001",
) -> PlanningAgentLoopResult:
    tool_result = ToolExecutionResult(
        tool_name=BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
        status=ToolExecutionStatus.SUCCEEDED,
        output=_workflow(status),
        metadata={
            "provider_calls": provider_calls,
            "recorded_tokens": 5,
            "elapsed_seconds": 0.01,
            "external_requests": provider_calls,
        },
    )
    return _planning_result(
        tool_results=[tool_result], plan_id=plan_id, trace_id=trace_id
    )


def _failed_result(
    *, retryable: bool, plan_id: str = "plan-001"
) -> PlanningAgentLoopResult:
    tool_result = ToolExecutionResult(
        tool_name=BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
        status=ToolExecutionStatus.FAILED,
        error_message="Safe controlled failure.",
        metadata={"error_code": "controlled_failure", "retryable": retryable},
    )
    return _planning_result(tool_results=[tool_result], plan_id=plan_id)


def _planning_result(
    *,
    tool_results: list[ToolExecutionResult],
    plan_id: str,
    trace_id: str | None = None,
) -> PlanningAgentLoopResult:
    step_results = [SimpleNamespace(tool_result=value) for value in tool_results]
    attempt = SimpleNamespace(
        run=SimpleNamespace(
            plan=SimpleNamespace(plan_id=plan_id),
            cycles=[SimpleNamespace(step_results=step_results)],
        )
    )
    return PlanningAgentLoopResult.model_construct(
        attempts=[attempt], status="goal_achieved", trace_id=trace_id
    )


class PlanningLoop:
    def __init__(
        self,
        results: list[PlanningAgentLoopResult],
        *,
        raises: bool = False,
        invalid: bool = False,
    ) -> None:
        self.results = list(results)
        self.raises = raises
        self.invalid = invalid
        self.requests: list[PlanningAgentLoopRequest] = []

    def run(self, request: PlanningAgentLoopRequest, **values: Any) -> object:
        del values
        self.requests.append(request)
        if self.raises:
            raise RuntimeError("planning secret")
        if self.invalid:
            return object()
        return self.results.pop(0)


def test_explicit_abstention_finishes_one_existing_planning_round() -> None:
    planning = PlanningLoop([_success_result(GroundedAnswerWorkflowStatus.ABSTAINED)])
    factory = RequestFactory()
    result = BoundedResearchPlanningLoop(
        planning_loop=planning, request_factory=factory
    ).run(request=_research_request())

    assert result.final_decision is ResearchAgentLoopDecision.ABSTAIN
    assert len(result.rounds) == 1
    assert result.rounds[0].plan_id == "plan-001"
    assert result.usage.tool_calls == 1
    assert result.trace_id == "trace-001"
    assert factory.calls == [(1, 0)]


def test_retryable_failure_replans_then_preserves_abstention() -> None:
    planning = PlanningLoop(
        [
            _failed_result(retryable=True, plan_id="plan-001"),
            _success_result(GroundedAnswerWorkflowStatus.ABSTAINED, plan_id="plan-002"),
        ]
    )
    factory = RequestFactory()
    result = BoundedResearchPlanningLoop(
        planning_loop=planning, request_factory=factory
    ).run(request=_research_request())

    assert [item.decision for item in result.rounds] == [
        ResearchAgentLoopDecision.REPLAN,
        ResearchAgentLoopDecision.ABSTAIN,
    ]
    assert result.usage.rounds == 2
    assert result.usage.tool_calls == 2
    assert factory.calls == [(1, 0), (2, 1)]


def test_nonretryable_failure_is_terminal_without_replan() -> None:
    result = BoundedResearchPlanningLoop(
        planning_loop=PlanningLoop([_failed_result(retryable=False)]),
        request_factory=RequestFactory(),
    ).run(request=_research_request())
    assert result.final_decision is ResearchAgentLoopDecision.TERMINAL_FAILURE
    assert result.usage.provider_calls == 0


def test_retryable_failure_at_round_ceiling_is_budget_exhausted() -> None:
    result = BoundedResearchPlanningLoop(
        planning_loop=PlanningLoop([_failed_result(retryable=True)]),
        request_factory=RequestFactory(),
    ).run(request=_research_request(maximum_rounds=1))
    assert result.final_decision is ResearchAgentLoopDecision.BUDGET_EXHAUSTED


def test_provider_ceiling_is_aggregated_before_decision() -> None:
    result = BoundedResearchPlanningLoop(
        planning_loop=PlanningLoop(
            [_success_result(GroundedAnswerWorkflowStatus.INCOMPLETE)]
        ),
        request_factory=RequestFactory(),
    ).run(request=_research_request(maximum_provider_calls=1))
    assert result.final_decision is ResearchAgentLoopDecision.BUDGET_EXHAUSTED
    assert result.usage.provider_calls == 1


def test_missing_grounded_tool_result_becomes_safe_terminal_observation() -> None:
    other = ToolExecutionResult(
        tool_name="other",
        status=ToolExecutionStatus.SUCCEEDED,
        output={"ignored": True},
    )
    result = BoundedResearchPlanningLoop(
        planning_loop=PlanningLoop(
            [_planning_result(tool_results=[other], plan_id="plan-001")]
        ),
        request_factory=RequestFactory(),
    ).run(request=_research_request())
    observation = result.rounds[0].observations[0]
    assert result.final_decision is ResearchAgentLoopDecision.TERMINAL_FAILURE
    assert observation.failure is not None
    assert observation.failure.code == "grounded_tool_not_executed"


def test_multiple_grounded_results_get_unique_observations_and_exact_usage() -> None:
    first = _failed_result(retryable=True)
    first_tool = first.attempts[0].run.cycles[0].step_results[0].tool_result
    second_tool = ToolExecutionResult(
        tool_name=BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
        status=ToolExecutionStatus.FAILED,
        error_message="Safe controlled failure.",
        metadata={"error_code": "second_failure", "retryable": False},
    )
    planning_result = _planning_result(
        tool_results=[first_tool, second_tool], plan_id="plan-001"
    )
    result = BoundedResearchPlanningLoop(
        planning_loop=PlanningLoop([planning_result]),
        request_factory=RequestFactory(),
    ).run(request=_research_request(maximum_tool_calls=3))
    ids = [item.observation_id for item in result.rounds[0].observations]
    assert ids == [
        "round-0001-observation-0001",
        "round-0001-observation-0002",
    ]
    assert result.usage.tool_calls == 2
    assert result.final_decision is ResearchAgentLoopDecision.HUMAN_REVIEW


def test_inner_planning_replans_are_rejected() -> None:
    with pytest.raises(BoundedResearchPlanningLoopError, match="must be zero"):
        BoundedResearchPlanningLoop(
            planning_loop=PlanningLoop([]),
            request_factory=RequestFactory(maximum_replans=1),
        ).run(request=_research_request())


def test_invalid_factory_loop_result_and_loop_exception_are_contained() -> None:
    with pytest.raises(BoundedResearchPlanningLoopError, match="request factory"):
        BoundedResearchPlanningLoop(
            planning_loop=PlanningLoop([]),
            request_factory=RequestFactory(invalid=True),
        ).run(request=_research_request())
    with pytest.raises(
        BoundedResearchPlanningLoopError, match="existing planning loop"
    ):
        BoundedResearchPlanningLoop(
            planning_loop=PlanningLoop([], raises=True),
            request_factory=RequestFactory(),
        ).run(request=_research_request())
    with pytest.raises(BoundedResearchPlanningLoopError, match="invalid result"):
        BoundedResearchPlanningLoop(
            planning_loop=PlanningLoop([], invalid=True),
            request_factory=RequestFactory(),
        ).run(request=_research_request())


def test_integration_requires_exact_research_request() -> None:
    with pytest.raises(TypeError, match="BoundedResearchAgentLoopRequest"):
        BoundedResearchPlanningLoop(
            planning_loop=PlanningLoop([]), request_factory=RequestFactory()
        ).run(request=object())  # type: ignore[arg-type]
