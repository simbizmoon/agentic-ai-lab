"""Tests for the integrated planning-agent pipeline."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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
from app.planning.planner_client import (
    PlannerClient,
    PlannerClientError,
)
from app.planning.planner_prompt_composer import (
    PlannerPromptComposer,
)
from app.planning.planning_agent_pipeline import (
    PlanningAgentPipeline,
    PlanningAgentPipelineError,
)
from app.planning.planning_service import PlanningService
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
    3,
    23,
    30,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed timestamp."""

    def now(self) -> datetime:
        return NOW


class FixedPlanIdGenerator(PlanIdGenerator):
    """Return one fixed plan ID."""

    def generate(self) -> str:
        return "plan-001"


class SuccessfulTool(Tool):
    """Return deterministic successful executions."""

    @property
    def name(self) -> str:
        return "python"

    def execute(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolExecutionStatus.SUCCEEDED,
            output={
                "step_id": request.step_id,
                "completed": True,
            },
        )


class FakePlannerClient(PlannerClient):
    """Return one configured planner output."""

    def __init__(
        self,
        *,
        error: PlannerClientError | None = None,
    ) -> None:
        self.error = error
        self.calls = 0

    def create_plan(
        self,
        *,
        request: PlanCreationRequest,
        prompt: PlannerPrompt,
    ) -> PlannerClientResult:
        self.calls += 1

        if self.error is not None:
            raise self.error

        return PlannerClientResult(
            output=PlanDraftOutput(
                reasoning_summary=(
                    "Implementation precedes verification."
                ),
                steps=[
                    PlanStepDraft(
                        step_id="step-1",
                        title="Implement",
                        description="Implement the feature.",
                        tool_name="python",
                    ),
                    PlanStepDraft(
                        step_id="step-2",
                        title="Verify",
                        description="Verify the feature.",
                        dependencies=["step-1"],
                        tool_name="python",
                    ),
                ],
            ),
            validation=(
                PlannerOutputValidationResult(
                    valid=True,
                    issues=[],
                    execution_order=[
                        "step-1",
                        "step-2",
                    ],
                )
            ),
            response_id="resp-001",
            model="test-model",
        )


def pipeline(
    planner_client: PlannerClient,
) -> PlanningAgentPipeline:
    """Return one deterministic integrated pipeline."""

    registry = ToolRegistry()
    registry.register(SuccessfulTool())

    planning_service = PlanningService(
        prompt_composer=PlannerPromptComposer(),
        planner_client=planner_client,
        plan_factory=PlanFactory(
            clock=FixedClock(),
            id_generator=FixedPlanIdGenerator(),
        ),
    )

    execution_service = PlanExecutionService(
        scheduler=PlanScheduler(),
        lifecycle=PlanLifecycleService(
            clock=FixedClock()
        ),
        step_executor=PlanStepExecutor(
            registry=registry
        ),
    )

    return PlanningAgentPipeline(
        planning_service=planning_service,
        plan_runner=PlanRunner(
            execution_service=execution_service
        ),
        plan_evaluator=PlanEvaluator(),
    )


def request() -> PlanningAgentRequest:
    """Return one integrated agent request."""

    return PlanningAgentRequest(
        planning=PlanCreationRequest(
            goal="Implement and verify the feature.",
            available_tools=["python"],
            maximum_steps=5,
            require_tool_for_each_step=True,
        )
    )


def test_pipeline_plans_executes_and_evaluates() -> None:
    planner_client = FakePlannerClient()

    result = pipeline(planner_client).run(
        request()
    )

    assert planner_client.calls == 1
    assert result.planning.created_plan.plan.plan_id == (
        "plan-001"
    )
    assert result.run.plan.status.value == "completed"
    assert result.evaluation.decision is (
        PlanEvaluationDecision.GOAL_ACHIEVED
    )
    assert len(result.run.cycles) == 2


def test_pipeline_preserves_planner_metadata() -> None:
    result = pipeline(
        FakePlannerClient()
    ).run(request())

    assert result.planning.planner_result.response_id == (
        "resp-001"
    )
    assert result.planning.planner_result.model == (
        "test-model"
    )


def test_pipeline_wraps_planning_failure() -> None:
    with pytest.raises(
        PlanningAgentPipelineError,
        match="planning stage failed",
    ):
        pipeline(
            FakePlannerClient(
                error=PlannerClientError(
                    "Planner API failed."
                )
            )
        ).run(request())
