"""Tests for end-to-end structured plan execution."""

from __future__ import annotations

from datetime import UTC, datetime

from app.memory.clock import Clock
from app.planning.plan_execution_service import (
    PlanExecutionService,
)
from app.planning.plan_lifecycle_service import (
    PlanLifecycleService,
)
from app.planning.plan_scheduler import PlanScheduler
from app.planning.plan_step_executor import (
    PlanStepExecutor,
)
from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_execution import (
    PlanExecutionStatus,
)
from app.schemas.plan_schedule import (
    PlanScheduleReason,
    PlanScheduleRequest,
)
from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from app.tools.planning_tool_registry import (
    ToolRegistry,
)
from app.tools.tool import Tool

NOW = datetime(
    2026,
    8,
    3,
    18,
    0,
    tzinfo=UTC,
)
UPDATED = datetime(
    2026,
    8,
    3,
    18,
    30,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed lifecycle timestamp."""

    def now(self) -> datetime:
        return UPDATED


class SuccessfulTool(Tool):
    """Return a successful tool result."""

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
            output={"step_id": request.step_id},
        )


class FailedTool(Tool):
    """Return a failed tool result."""

    @property
    def name(self) -> str:
        return "failed"

    def execute(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolExecutionStatus.FAILED,
            error_message="Tool failed.",
        )


def step(
    *,
    step_id: str,
    dependencies: list[str] | None = None,
    status: PlanStepStatus,
    tool_name: str,
) -> PlanStep:
    """Return one plan step."""

    return PlanStep(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete {step_id}.",
        dependencies=dependencies or [],
        status=status,
        tool_name=tool_name,
    )


def plan(
    *,
    steps: list[PlanStep],
    status: PlanStatus = PlanStatus.IN_PROGRESS,
) -> Plan:
    """Return one plan."""

    return Plan(
        plan_id="plan-001",
        goal="Execute the plan.",
        status=status,
        steps=steps,
        created_at=NOW,
        updated_at=NOW,
    )


def service(
    *tools: Tool,
) -> PlanExecutionService:
    """Return one execution service."""

    registry = ToolRegistry()

    for tool in tools:
        registry.register(tool)

    return PlanExecutionService(
        scheduler=PlanScheduler(),
        lifecycle=PlanLifecycleService(
            clock=FixedClock()
        ),
        step_executor=PlanStepExecutor(
            registry=registry
        ),
    )


def test_successful_step_completes_plan() -> None:
    result = service(
        SuccessfulTool()
    ).execute_next(
        plan=plan(
            steps=[
                step(
                    step_id="step-1",
                    status=PlanStepStatus.READY,
                    tool_name="python",
                )
            ]
        )
    )

    assert result.status is (
        PlanExecutionStatus.STEP_SUCCEEDED
    )
    assert result.plan.status is PlanStatus.COMPLETED
    assert result.plan.steps[0].status is (
        PlanStepStatus.COMPLETED
    )


def test_successful_step_unlocks_next_step() -> None:
    result = service(
        SuccessfulTool()
    ).execute_next(
        plan=plan(
            steps=[
                step(
                    step_id="step-1",
                    status=PlanStepStatus.READY,
                    tool_name="python",
                ),
                step(
                    step_id="step-2",
                    dependencies=["step-1"],
                    status=PlanStepStatus.PENDING,
                    tool_name="python",
                ),
            ]
        )
    )

    assert result.plan.steps[0].status is (
        PlanStepStatus.COMPLETED
    )
    assert result.plan.steps[1].status is (
        PlanStepStatus.READY
    )
    assert result.plan.status is (
        PlanStatus.IN_PROGRESS
    )


def test_failed_step_fails_plan() -> None:
    result = service(
        FailedTool()
    ).execute_next(
        plan=plan(
            steps=[
                step(
                    step_id="step-1",
                    status=PlanStepStatus.READY,
                    tool_name="failed",
                )
            ]
        )
    )

    assert result.status is (
        PlanExecutionStatus.STEP_FAILED
    )
    assert result.plan.status is PlanStatus.FAILED
    assert result.plan.steps[0].status is (
        PlanStepStatus.FAILED
    )


def test_nothing_scheduled_preserves_plan() -> None:
    original = plan(
        status=PlanStatus.DRAFT,
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.READY,
                tool_name="python",
            )
        ],
    )

    result = service(
        SuccessfulTool()
    ).execute_next(plan=original)

    assert result.status is (
        PlanExecutionStatus.NOTHING_SCHEDULED
    )
    assert result.schedule.reason is (
        PlanScheduleReason.PLAN_NOT_IN_PROGRESS
    )
    assert result.plan == original


def test_parallel_execution_runs_selected_steps() -> None:
    result = service(
        SuccessfulTool()
    ).execute_next(
        plan=plan(
            steps=[
                step(
                    step_id="step-1",
                    status=PlanStepStatus.READY,
                    tool_name="python",
                ),
                step(
                    step_id="step-2",
                    status=PlanStepStatus.READY,
                    tool_name="python",
                ),
            ]
        ),
        schedule_request=PlanScheduleRequest(
            allow_parallel_steps=True,
            maximum_selected_steps=2,
            allow_new_steps_while_active=True,
        ),
    )

    assert [
        value.step_id
        for value in result.step_results
    ] == [
        "step-1",
        "step-2",
    ]
    assert result.plan.status is PlanStatus.COMPLETED


def test_original_plan_is_not_mutated() -> None:
    original = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.READY,
                tool_name="python",
            )
        ]
    )

    result = service(
        SuccessfulTool()
    ).execute_next(plan=original)

    assert original.steps[0].status is (
        PlanStepStatus.READY
    )
    assert result.plan.steps[0].status is (
        PlanStepStatus.COMPLETED
    )
