"""Offline E2E tests through the real planning pipeline and research loop."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.memory.clock import Clock
from app.planning.plan_evaluator import PlanEvaluator
from app.planning.plan_execution_service import PlanExecutionService
from app.planning.plan_factory import PlanFactory
from app.planning.plan_id_generator import PlanIdGenerator
from app.planning.plan_lifecycle_service import PlanLifecycleService
from app.planning.plan_runner import PlanRunner
from app.planning.plan_scheduler import PlanScheduler
from app.planning.plan_step_executor import PlanStepExecutor
from app.planning.planner_client import PlannerClient
from app.planning.planner_prompt_composer import PlannerPromptComposer
from app.planning.planning_agent_loop import PlanningAgentLoop
from app.planning.planning_agent_pipeline import PlanningAgentPipeline
from app.planning.planning_service import PlanningService
from app.planning.replan_context_service import ReplanContextService
from app.planning.replanning_service import ReplanningService
from app.rag.context_builder import build_rag_context
from app.research.bounded_answer_citation_verifier import BoundedAnswerCitationVerifier
from app.research.bounded_grounded_answer_agent_tool import (
    BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
    BoundedGroundedAnswerAgentTool,
)
from app.research.bounded_research_planning_loop import BoundedResearchPlanningLoop
from app.schemas.answer_citation_validation import (
    AnswerCitationValidationBudget,
    AnswerCitationValidationRequest,
)
from app.schemas.bounded_grounded_answer_workflow import (
    BoundedGroundedAnswerWorkflowResult,
    GroundedAnswerGenerationBudget,
    GroundedAnswerGenerationUsage,
    GroundedAnswerWorkflowFailure,
    GroundedAnswerWorkflowFailureStage,
    GroundedAnswerWorkflowRequest,
    GroundedAnswerWorkflowStatus,
)
from app.schemas.bounded_research_agent_loop import (
    BoundedResearchAgentLoopBudget,
    BoundedResearchAgentLoopRequest,
    ResearchAgentLoopDecision,
)
from app.schemas.grounded_answer_result import GroundedAnswerResult
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planner_client_result import PlannerClientResult
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import PlannerOutputValidationResult
from app.schemas.planner_prompt import PlannerPrompt
from app.schemas.planning_agent_loop import PlanningAgentLoopRequest
from app.schemas.planning_agent_request import PlanningAgentRequest
from app.schemas.rag_context_packing import (
    RagContextPackingBudget,
    RagContextPackingRequest,
    RagContextPackingResult,
    RagContextPackingUsage,
)
from app.tools.planning_tool_registry import ToolRegistry

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)


class FixedClock(Clock):
    def now(self) -> datetime:
        return NOW


class SequentialPlanIdGenerator(PlanIdGenerator):
    def __init__(self) -> None:
        self.value = 0

    def generate(self) -> str:
        self.value += 1
        return f"stage7-e2e-plan-{self.value:03d}"


class LocalPlannerClient(PlannerClient):
    def __init__(self, workflow_request: GroundedAnswerWorkflowRequest) -> None:
        self.workflow_request = workflow_request
        self.calls = 0

    def create_plan(
        self, *, request: PlanCreationRequest, prompt: PlannerPrompt
    ) -> PlannerClientResult:
        del request, prompt
        self.calls += 1
        return PlannerClientResult(
            output=PlanDraftOutput(
                reasoning_summary="Run the bounded grounded-answer workflow once.",
                steps=[
                    PlanStepDraft(
                        step_id="grounded-answer-step",
                        title="Run bounded grounded answer",
                        description="Use the packed evidence under fixed budgets.",
                        tool_name=BOUNDED_GROUNDED_ANSWER_TOOL_NAME,
                        expected_output="One bounded grounded workflow result",
                        metadata={"workflow_request": self.workflow_request},
                    )
                ],
            ),
            validation=PlannerOutputValidationResult(
                valid=True, issues=[], execution_order=["grounded-answer-step"]
            ),
            response_id=f"local-plan-response-{self.calls}",
            model="controlled-local-planner",
        )


class NoEvidenceEvaluator:
    def evaluate(self, **values: Any) -> object:
        raise AssertionError(f"empty evidence must not be evaluated: {values}")


class SequencedWorkflow:
    def __init__(self, results: list[BoundedGroundedAnswerWorkflowResult]) -> None:
        self.results = list(results)
        self.calls = 0

    def run(
        self, *, request: GroundedAnswerWorkflowRequest
    ) -> BoundedGroundedAnswerWorkflowResult:
        self.calls += 1
        result = self.results.pop(0)
        assert result.request == request
        return result


class ResearchRequestFactory:
    def __init__(self, workflow_request: GroundedAnswerWorkflowRequest) -> None:
        self.workflow_request = workflow_request
        self.calls: list[tuple[int, int]] = []

    def create(
        self,
        *,
        round_number: int,
        research_request: BoundedResearchAgentLoopRequest,
        previous_rounds: list[object],
    ) -> PlanningAgentLoopRequest:
        self.calls.append((round_number, len(previous_rounds)))
        return PlanningAgentLoopRequest(
            initial=PlanningAgentRequest(
                planning=PlanCreationRequest(
                    goal=research_request.goal,
                    constraints=list(research_request.constraints),
                    available_tools=list(research_request.allowed_tools),
                    maximum_steps=1,
                    require_tool_for_each_step=True,
                    metadata={"research_round": round_number},
                )
            ),
            maximum_replans=0,
        )


def _workflow_request() -> GroundedAnswerWorkflowRequest:
    packing_request = RagContextPackingRequest(
        candidates=[],
        budget=RagContextPackingBudget(
            maximum_items=1,
            maximum_utf8_bytes=100,
            maximum_estimated_tokens=20,
            token_estimator_id="stage7-step6-offline-v1",
        ),
    )
    return GroundedAnswerWorkflowRequest(
        question="What is supported by the bounded evidence?",
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


def _generation_failure(
    request: GroundedAnswerWorkflowRequest,
) -> BoundedGroundedAnswerWorkflowResult:
    return BoundedGroundedAnswerWorkflowResult(
        request=request,
        status=GroundedAnswerWorkflowStatus.GENERATION_FAILED,
        generation_usage=GroundedAnswerGenerationUsage(
            attempts=1, recorded_tokens=0, elapsed_seconds=0.01
        ),
        generation_budget_exhausted=False,
        answer=None,
        citation_validation=None,
        abstention_detected=False,
        failure=GroundedAnswerWorkflowFailure(
            stage=GroundedAnswerWorkflowFailureStage.GENERATION,
            code="temporary_local_failure",
            safe_message="The controlled generator temporarily failed.",
            retryable=True,
        ),
    )


def _abstention(
    request: GroundedAnswerWorkflowRequest,
) -> BoundedGroundedAnswerWorkflowResult:
    context = build_rag_context([])
    answer = GroundedAnswerResult(
        question=request.question,
        answer="The supplied evidence is insufficient.",
        citations=[],
        cited_ids=[],
        response_id="local-answer-response",
        model_name="controlled-local-generator",
        evidence_available=False,
    )
    validation = BoundedAnswerCitationVerifier(evaluator=NoEvidenceEvaluator()).verify(
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
        status=GroundedAnswerWorkflowStatus.ABSTAINED,
        generation_usage=GroundedAnswerGenerationUsage(
            attempts=1, recorded_tokens=6, elapsed_seconds=0.01
        ),
        generation_budget_exhausted=False,
        answer=answer,
        citation_validation=validation,
        abstention_detected=True,
    )


def _real_loop(
    *, workflow: SequencedWorkflow, planner_client: LocalPlannerClient
) -> PlanningAgentLoop:
    registry = ToolRegistry()
    registry.register(
        BoundedGroundedAnswerAgentTool(
            workflow=workflow, provider_calls_are_external=False
        )
    )
    plan_factory = PlanFactory(
        clock=FixedClock(), id_generator=SequentialPlanIdGenerator()
    )
    pipeline = PlanningAgentPipeline(
        planning_service=PlanningService(
            prompt_composer=PlannerPromptComposer(),
            planner_client=planner_client,
            plan_factory=plan_factory,
        ),
        plan_runner=PlanRunner(
            execution_service=PlanExecutionService(
                scheduler=PlanScheduler(),
                lifecycle=PlanLifecycleService(clock=FixedClock()),
                step_executor=PlanStepExecutor(registry=registry),
            )
        ),
        plan_evaluator=PlanEvaluator(),
    )
    return PlanningAgentLoop(
        pipeline=pipeline,
        replan_context_service=ReplanContextService(),
        replanning_service=ReplanningService(
            prompt_composer=PlannerPromptComposer(),
            planner_client=planner_client,
            plan_factory=plan_factory,
        ),
    )


def _research_budget(*, maximum_rounds: int) -> BoundedResearchAgentLoopBudget:
    return BoundedResearchAgentLoopBudget(
        maximum_rounds=maximum_rounds,
        maximum_tool_calls=maximum_rounds,
        maximum_provider_calls=maximum_rounds,
        maximum_recorded_tokens=100,
        maximum_elapsed_seconds=10.0,
        maximum_external_requests=0,
    )


def test_real_pipeline_replans_after_retryable_evidence_failure_then_abstains() -> None:
    workflow_request = _workflow_request()
    workflow = SequencedWorkflow(
        [_generation_failure(workflow_request), _abstention(workflow_request)]
    )
    planner_client = LocalPlannerClient(workflow_request)
    request_factory = ResearchRequestFactory(workflow_request)
    result = BoundedResearchPlanningLoop(
        planning_loop=_real_loop(workflow=workflow, planner_client=planner_client),
        request_factory=request_factory,
    ).run(
        request=BoundedResearchAgentLoopRequest(
            goal="Answer only from bounded grounded evidence",
            constraints=["Abstain when evidence is absent"],
            allowed_tools=[BOUNDED_GROUNDED_ANSWER_TOOL_NAME],
            budget=_research_budget(maximum_rounds=2),
        )
    )

    assert [item.decision for item in result.rounds] == [
        ResearchAgentLoopDecision.REPLAN,
        ResearchAgentLoopDecision.ABSTAIN,
    ]
    assert [item.plan_id for item in result.rounds] == [
        "stage7-e2e-plan-001",
        "stage7-e2e-plan-002",
    ]
    assert result.usage.rounds == 2
    assert result.usage.tool_calls == 2
    assert result.usage.provider_calls == 2
    assert result.usage.recorded_tokens == 6
    assert result.usage.external_requests == 0
    assert workflow.calls == 2
    assert planner_client.calls == 2
    assert request_factory.calls == [(1, 0), (2, 1)]
    assert result.rounds[1].observations[0].workflow_result is not None
    assert result.rounds[1].observations[0].workflow_result.status is (
        GroundedAnswerWorkflowStatus.ABSTAINED
    )


def test_real_pipeline_stops_at_research_round_budget_before_second_plan() -> None:
    workflow_request = _workflow_request()
    workflow = SequencedWorkflow([_generation_failure(workflow_request)])
    planner_client = LocalPlannerClient(workflow_request)
    result = BoundedResearchPlanningLoop(
        planning_loop=_real_loop(workflow=workflow, planner_client=planner_client),
        request_factory=ResearchRequestFactory(workflow_request),
    ).run(
        request=BoundedResearchAgentLoopRequest(
            goal="Answer only from bounded grounded evidence",
            allowed_tools=[BOUNDED_GROUNDED_ANSWER_TOOL_NAME],
            budget=_research_budget(maximum_rounds=1),
        )
    )
    assert result.final_decision is ResearchAgentLoopDecision.BUDGET_EXHAUSTED
    assert result.usage.rounds == 1
    assert workflow.calls == 1
    assert planner_client.calls == 1
