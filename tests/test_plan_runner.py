"""Tests for repeated structured plan execution."""

from __future__ import annotations

from datetime import UTC, datetime

from app.memory.clock import Clock
from app.planning.plan_execution_service import (
    PlanExecutionService,
)
from app.planning.plan_lifecycle_service import (
    PlanLifecycleService,
)
from app.planning.plan_runner import PlanRunner
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
from app.schemas.plan_run import (
    PlanRunRequest,
    PlanRunStatus,
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
    19,
    0,
    tzinfo=UTC,
)
UPDATED = datetime(
    2026,
    8,
    3,
    19,
    30,
    tzinfo=UTC,
)


class FixedClock(Clock):
    """Return one fixed lifecycle timestamp."""

    def now(self) -> datetime:
        return UPDATED


class SuccessfulTool(Tool):
    """Return successful deterministic executions."""

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
    """Return one deterministic failed execution."""

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
    """Return one structured plan."""

    return Plan(
        plan_id="plan-001",
        goal="Run the complete plan.",
        status=status,
        steps=steps,
        created_at=NOW,
        updated_at=NOW,
    )


def runner(
    *tools: Tool,
) -> PlanRunner:
    """Return one deterministic plan runner."""

    registry = ToolRegistry()

    for tool in tools:
        registry.register(tool)

    execution_service = PlanExecutionService(
        scheduler=PlanScheduler(),
        lifecycle=PlanLifecycleService(
            clock=FixedClock()
        ),
        step_executor=PlanStepExecutor(
            registry=registry
        ),
    )

    return PlanRunner(
        execution_service=execution_service
    )


def test_runner_completes_linear_plan() -> None:
    result = runner(
        SuccessfulTool()
    ).run(
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
                step(
                    step_id="step-3",
                    dependencies=["step-2"],
                    status=PlanStepStatus.PENDING,
                    tool_name="python",
                ),
            ]
        )
    )

    assert result.status is PlanRunStatus.COMPLETED
    assert result.plan.status is PlanStatus.COMPLETED
    assert result.executed_step_ids == [
        "step-1",
        "step-2",
        "step-3",
    ]
    assert len(result.cycles) == 3


def test_runner_stops_after_failed_step() -> None:
    result = runner(
        FailedTool()
    ).run(
        plan=plan(
            steps=[
                step(
                    step_id="step-1",
                    status=PlanStepStatus.READY,
                    tool_name="failed",
                ),
                step(
                    step_id="step-2",
                    dependencies=["step-1"],
                    status=PlanStepStatus.PENDING,
                    tool_name="failed",
                ),
            ]
        )
    )

    assert result.status is PlanRunStatus.FAILED
    assert result.plan.status is PlanStatus.FAILED
    assert result.executed_step_ids == ["step-1"]
    assert len(result.cycles) == 1


def test_runner_returns_completed_terminal_plan() -> None:
    result = runner().run(
        plan=plan(
            status=PlanStatus.COMPLETED,
            steps=[
                step(
                    step_id="step-1",
                    status=PlanStepStatus.COMPLETED,
                    tool_name="python",
                )
            ],
        )
    )

    assert result.status is PlanRunStatus.COMPLETED
    assert result.cycles == []
    assert result.executed_step_ids == []


def test_runner_returns_cancelled_terminal_plan() -> None:
    result = runner().run(
        plan=plan(
            status=PlanStatus.CANCELLED,
            steps=[
                step(
                    step_id="step-1",
                    status=PlanStepStatus.SKIPPED,
                    tool_name="python",
                )
            ],
        )
    )

    assert result.status is PlanRunStatus.CANCELLED
    assert result.cycles == []


def test_runner_reports_blocked_plan() -> None:
    result = runner().run(
        plan=plan(
            status=PlanStatus.DRAFT,
            steps=[
                step(
                    step_id="step-1",
                    status=PlanStepStatus.READY,
                    tool_name="python",
                )
            ],
        )
    )

    assert result.status is PlanRunStatus.BLOCKED
    assert len(result.cycles) == 1


def test_runner_respects_cycle_limit() -> None:
    result = runner(
        SuccessfulTool()
    ).run(
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
        ),
        request=PlanRunRequest(
            maximum_cycles=1
        ),
    )

    assert result.status is (
        PlanRunStatus.CYCLE_LIMIT_REACHED
    )
    assert result.executed_step_ids == ["step-1"]
    assert result.plan.status is (
        PlanStatus.IN_PROGRESS
    )


def test_runner_does_not_mutate_original_plan() -> None:
    original = plan(
        steps=[
            step(
                step_id="step-1",
                status=PlanStepStatus.READY,
                tool_name="python",
            )
        ]
    )

    result = runner(
        SuccessfulTool()
    ).run(plan=original)

    assert original.steps[0].status is (
        PlanStepStatus.READY
    )
    assert result.plan.steps[0].status is (
        PlanStepStatus.COMPLETED
    )
