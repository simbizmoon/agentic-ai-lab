"""End-to-end tests for bounded automatic replanning."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime

from app.memory.clock import Clock
from app.planning.plan_evaluator import PlanEvaluator
from app.planning.plan_execution_service import (
    PlanExecutionService,
)
from app.planning.plan_factory import PlanFactory
from app.planning.plan_id_generator import (
    PlanIdGenerator,
)
from app.planning.plan_lifecycle_service import (
    PlanLifecycleService,
)
from app.planning.plan_runner import PlanRunner
from app.planning.plan_scheduler import PlanScheduler
from app.planning.plan_step_executor import (
    PlanStepExecutor,
)
from app.planning.planner_client import PlannerClient
from app.planning.planner_prompt_composer import (
    PlannerPromptComposer,
)
from app.planning.planning_agent_loop import (
    PlanningAgentLoop,
)
from app.planning.planning_agent_pipeline import (
    PlanningAgentPipeline,
)
from app.planning.planning_service import PlanningService
from app.planning.replan_context_service import (
    ReplanContextService,
)
from app.planning.replanning_service import (
    ReplanningService,
)
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_evaluation import (
    PlanEvaluationDecision,
)
from app.schemas.plan_request import PlanCreationRequest
from app.schemas.planner_client_result import (
    PlannerClientResult,
)
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import (
    PlannerOutputValidationResult,
)
from app.schemas.planner_prompt import PlannerPrompt
from app.schemas.planning_agent_loop import (
    PlanningAgentLoopRequest,
    PlanningAgentLoopStatus,
)
from app.schemas.planning_agent_request import (
    PlanningAgentRequest,
)
from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from app.tools.planning_tool_registry import ToolRegistry
from app.tools.tool import Tool

NOW = datetime(
    2026,
    8,
    4,
    0,
    30,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed timestamp."""

    def now(self) -> datetime:
        return NOW


class SequentialPlanIdGenerator(PlanIdGenerator):
    """Return deterministic sequential plan IDs."""

    def __init__(self) -> None:
        self._next_number = 1

    def generate(self) -> str:
        plan_id = f"plan-{self._next_number:03d}"
        self._next_number += 1
        return plan_id


class SequencedTool(Tool):
    """Return configured execution outcomes in order."""

    def __init__(
        self,
        statuses: list[ToolExecutionStatus],
    ) -> None:
        self._statuses = deque(statuses)
        self.calls = 0

    @property
    def name(self) -> str:
        return "worker"

    def execute(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        self.calls += 1

        if not self._statuses:
            raise AssertionError(
                "no configured tool status remains"
            )

        status = self._statuses.popleft()

        if status is ToolExecutionStatus.FAILED:
            return ToolExecutionResult(
                tool_name=self.name,
                status=status,
                error_message=(
                    f"Execution failed for {request.step_id}."
                ),
            )

        return ToolExecutionResult(
            tool_name=self.name,
            status=status,
            output={
                "step_id": request.step_id,
                "completed": True,
            },
        )


class SequencedPlannerClient(PlannerClient):
    """Return configured planner outputs in call order."""

    def __init__(
        self,
        outputs: list[PlanDraftOutput],
    ) -> None:
        self._outputs = deque(outputs)
        self.calls: list[
            tuple[PlanCreationRequest, PlannerPrompt]
        ] = []

    def create_plan(
        self,
        *,
        request: PlanCreationRequest,
        prompt: PlannerPrompt,
    ) -> PlannerClientResult:
        self.calls.append((request, prompt))

        if not self._outputs:
            raise AssertionError(
                "no configured planner output remains"
            )

        output = self._outputs.popleft()

        return PlannerClientResult(
            output=output,
            validation=PlannerOutputValidationResult(
                valid=True,
                issues=[],
                execution_order=[
                    step.step_id
                    for step in output.steps
                ],
            ),
            response_id=f"resp-{len(self.calls):03d}",
            model="test-model",
        )


def planner_output(
    *,
    title: str,
) -> PlanDraftOutput:
    """Return one executable single-step planner output."""

    return PlanDraftOutput(
        reasoning_summary=(
            "Use one deterministic execution step."
        ),
        steps=[
            PlanStepDraft(
                step_id="step-1",
                title=title,
                description=f"{title}.",
                tool_name="worker",
                expected_output="The operation completes.",
            )
        ],
    )


def build_loop(
    *,
    planner_client: SequencedPlannerClient,
    tool: SequencedTool,
) -> PlanningAgentLoop:
    """Assemble one deterministic planning-agent loop."""

    id_generator = SequentialPlanIdGenerator()
    clock = FixedClock()

    prompt_composer = PlannerPromptComposer()

    planning_service = PlanningService(
        prompt_composer=prompt_composer,
        planner_client=planner_client,
        plan_factory=PlanFactory(
            clock=clock,
            id_generator=id_generator,
        ),
    )

    replanning_service = ReplanningService(
        prompt_composer=prompt_composer,
        planner_client=planner_client,
        plan_factory=PlanFactory(
            clock=clock,
            id_generator=id_generator,
        ),
    )

    registry = ToolRegistry()
    registry.register(tool)

    execution_service = PlanExecutionService(
        scheduler=PlanScheduler(),
        lifecycle=PlanLifecycleService(
            clock=clock
        ),
        step_executor=PlanStepExecutor(
            registry=registry
        ),
    )

    plan_runner = PlanRunner(
        execution_service=execution_service
    )

    pipeline = PlanningAgentPipeline(
        planning_service=planning_service,
        plan_runner=plan_runner,
        plan_evaluator=PlanEvaluator(),
    )

    return PlanningAgentLoop(
        pipeline=pipeline,
        replan_context_service=(
            ReplanContextService()
        ),
        replanning_service=replanning_service,
    )


def loop_request(
    *,
    maximum_replans: int = 2,
) -> PlanningAgentLoopRequest:
    """Return one bounded automatic-replanning request."""

    return PlanningAgentLoopRequest(
        initial=PlanningAgentRequest(
            planning=PlanCreationRequest(
                goal="Complete the requested operation.",
                available_tools=["worker"],
                maximum_steps=3,
                require_tool_for_each_step=True,
            )
        ),
        maximum_replans=maximum_replans,
    )


def test_loop_replans_failed_plan_and_then_succeeds() -> None:
    planner_client = SequencedPlannerClient(
        outputs=[
            planner_output(
                title="Use original approach"
            ),
            planner_output(
                title="Use replacement approach"
            ),
        ]
    )
    tool = SequencedTool(
        statuses=[
            ToolExecutionStatus.FAILED,
            ToolExecutionStatus.SUCCEEDED,
        ]
    )

    result = build_loop(
        planner_client=planner_client,
        tool=tool,
    ).run(loop_request())

    assert result.status is (
        PlanningAgentLoopStatus.GOAL_ACHIEVED
    )
    assert len(result.attempts) == 2

    first, second = result.attempts

    assert first.run.plan.plan_id == "plan-001"
    assert first.evaluation.decision is (
        PlanEvaluationDecision.REPLAN_REQUIRED
    )

    assert second.run.plan.plan_id == "plan-002"
    assert second.source_plan_id == "plan-001"
    assert second.evaluation.decision is (
        PlanEvaluationDecision.GOAL_ACHIEVED
    )

    assert len(planner_client.calls) == 2
    assert tool.calls == 2


def test_loop_does_not_replan_successful_initial_plan() -> None:
    planner_client = SequencedPlannerClient(
        outputs=[
            planner_output(
                title="Use successful approach"
            )
        ]
    )
    tool = SequencedTool(
        statuses=[
            ToolExecutionStatus.SUCCEEDED
        ]
    )

    result = build_loop(
        planner_client=planner_client,
        tool=tool,
    ).run(loop_request())

    assert result.status is (
        PlanningAgentLoopStatus.GOAL_ACHIEVED
    )
    assert len(result.attempts) == 1
    assert len(planner_client.calls) == 1
    assert tool.calls == 1


def test_loop_respects_zero_replan_limit() -> None:
    planner_client = SequencedPlannerClient(
        outputs=[
            planner_output(
                title="Use failing approach"
            )
        ]
    )
    tool = SequencedTool(
        statuses=[
            ToolExecutionStatus.FAILED
        ]
    )

    result = build_loop(
        planner_client=planner_client,
        tool=tool,
    ).run(
        loop_request(maximum_replans=0)
    )

    assert result.status is (
        PlanningAgentLoopStatus
        .REPLAN_LIMIT_REACHED
    )
    assert len(result.attempts) == 1
    assert len(planner_client.calls) == 1


def test_loop_stops_after_configured_replans() -> None:
    planner_client = SequencedPlannerClient(
        outputs=[
            planner_output(title="Approach one"),
            planner_output(title="Approach two"),
        ]
    )
    tool = SequencedTool(
        statuses=[
            ToolExecutionStatus.FAILED,
            ToolExecutionStatus.FAILED,
        ]
    )

    result = build_loop(
        planner_client=planner_client,
        tool=tool,
    ).run(
        loop_request(maximum_replans=1)
    )

    assert result.status is (
        PlanningAgentLoopStatus
        .REPLAN_LIMIT_REACHED
    )
    assert len(result.attempts) == 2
    assert [
        attempt.run.plan.plan_id
        for attempt in result.attempts
    ] == [
        "plan-001",
        "plan-002",
    ]
    assert all(
        attempt.evaluation.decision
        is PlanEvaluationDecision.REPLAN_REQUIRED
        for attempt in result.attempts
    )


def test_replan_prompt_references_failed_source_plan() -> None:
    planner_client = SequencedPlannerClient(
        outputs=[
            planner_output(title="Original approach"),
            planner_output(title="Replacement approach"),
        ]
    )
    tool = SequencedTool(
        statuses=[
            ToolExecutionStatus.FAILED,
            ToolExecutionStatus.SUCCEEDED,
        ]
    )

    build_loop(
        planner_client=planner_client,
        tool=tool,
    ).run(loop_request())

    replan_prompt = planner_client.calls[1][1]

    assert replan_prompt.source_plan_id == "plan-001"
    assert (
        "Execution failed for step-1."
        in replan_prompt.messages[1].content
    )
