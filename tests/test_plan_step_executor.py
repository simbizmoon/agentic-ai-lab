"""Tests for connecting plan steps to registered tools."""

from __future__ import annotations

from app.planning.plan_step_executor import (
    PlanStepExecutor,
)
from app.schemas.plan import (
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_step_execution import (
    PlanStepExecutionStatus,
)
from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)
from app.tools.planning_tool_registry import ToolRegistry
from app.tools.tool import (
    Tool,
    ToolExecutionError,
)


class SuccessfulTool(Tool):
    """Return one successful deterministic result."""

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
                "arguments": request.arguments,
            },
        )


class FailingTool(Tool):
    """Return one normalized failed result."""

    @property
    def name(self) -> str:
        return "failing"

    def execute(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolExecutionStatus.FAILED,
            error_message="Tool failed.",
        )


class RaisingTool(Tool):
    """Raise one execution exception."""

    @property
    def name(self) -> str:
        return "raising"

    def execute(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        raise ToolExecutionError(
            "Unexpected failure."
        )


class MismatchedTool(Tool):
    """Return a result with an invalid tool name."""

    @property
    def name(self) -> str:
        return "declared"

    def execute(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            tool_name="different",
            status=ToolExecutionStatus.SUCCEEDED,
            output={},
        )


def step(
    *,
    tool_name: str | None = "python",
    status: PlanStepStatus = PlanStepStatus.READY,
) -> PlanStep:
    """Return one plan step."""

    return PlanStep(
        step_id="step-1",
        title="Execute Python",
        description="Run the configured operation.",
        status=status,
        tool_name=tool_name,
        expected_output="A deterministic result.",
        metadata={"source": "test"},
    )


def executor_with(
    *tools: Tool,
) -> PlanStepExecutor:
    """Return an executor with registered tools."""

    registry = ToolRegistry()

    for tool in tools:
        registry.register(tool)

    return PlanStepExecutor(registry=registry)


def test_executor_runs_registered_tool() -> None:
    result = executor_with(
        SuccessfulTool()
    ).execute(step())

    assert result.status is (
        PlanStepExecutionStatus.SUCCEEDED
    )
    assert result.tool_result is not None
    assert result.tool_result.output[
        "step_id"
    ] == "step-1"


def test_executor_rejects_non_executable_status() -> None:
    result = executor_with(
        SuccessfulTool()
    ).execute(
        step(status=PlanStepStatus.PENDING)
    )

    assert result.status is (
        PlanStepExecutionStatus
        .STEP_NOT_EXECUTABLE
    )


def test_executor_reports_missing_tool_name() -> None:
    result = executor_with().execute(
        step(tool_name=None)
    )

    assert result.status is (
        PlanStepExecutionStatus.TOOL_NOT_FOUND
    )


def test_executor_reports_unregistered_tool() -> None:
    result = executor_with().execute(
        step(tool_name="missing")
    )

    assert result.status is (
        PlanStepExecutionStatus.TOOL_NOT_FOUND
    )


def test_executor_propagates_normalized_failure() -> None:
    result = executor_with(
        FailingTool()
    ).execute(
        step(tool_name="failing")
    )

    assert result.status is (
        PlanStepExecutionStatus.FAILED
    )
    assert result.tool_result is not None
    assert result.error_message == "Tool failed."


def test_executor_converts_exception_to_failure() -> None:
    result = executor_with(
        RaisingTool()
    ).execute(
        step(tool_name="raising")
    )

    assert result.status is (
        PlanStepExecutionStatus.FAILED
    )
    assert "ToolExecutionError" in result.error_message


def test_executor_rejects_mismatched_tool_result() -> None:
    result = executor_with(
        MismatchedTool()
    ).execute(
        step(tool_name="declared")
    )

    assert result.status is (
        PlanStepExecutionStatus.FAILED
    )
    assert "mismatched" in result.error_message
