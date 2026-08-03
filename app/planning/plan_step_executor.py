"""Execution service connecting plan steps to registered tools."""

from __future__ import annotations

from app.schemas.plan import (
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_step_execution import (
    PlanStepExecutionResult,
    PlanStepExecutionStatus,
)
from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionStatus,
)
from app.tools.planning_tool_registry import ToolRegistry
from app.tools.tool import ToolExecutionError


class PlanStepExecutor:
    """Execute one ready or in-progress plan step."""

    def __init__(
        self,
        *,
        registry: ToolRegistry,
    ) -> None:
        self._registry = registry

    @property
    def registry(self) -> ToolRegistry:
        """Return the configured tool registry."""

        return self._registry

    def execute(
        self,
        step: PlanStep,
    ) -> PlanStepExecutionResult:
        """Execute one plan step using its registered tool."""

        if step.status not in {
            PlanStepStatus.READY,
            PlanStepStatus.IN_PROGRESS,
        }:
            return PlanStepExecutionResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status=(
                    PlanStepExecutionStatus
                    .STEP_NOT_EXECUTABLE
                ),
                error_message=(
                    f"step {step.step_id} is not executable "
                    f"from status {step.status.value}"
                ),
            )

        if step.tool_name is None:
            return PlanStepExecutionResult(
                step_id=step.step_id,
                tool_name=None,
                status=(
                    PlanStepExecutionStatus
                    .TOOL_NOT_FOUND
                ),
                error_message=(
                    f"step {step.step_id} has no tool"
                ),
            )

        tool = self.registry.get(step.tool_name)

        if tool is None:
            return PlanStepExecutionResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status=(
                    PlanStepExecutionStatus
                    .TOOL_NOT_FOUND
                ),
                error_message=(
                    f"tool is not registered: "
                    f"{step.tool_name}"
                ),
            )

        request = ToolExecutionRequest(
            step_id=step.step_id,
            description=step.description,
            arguments={
                "title": step.title,
                "expected_output": step.expected_output,
                "metadata": dict(step.metadata),
            },
        )

        try:
            tool_result = tool.execute(request)
        except ToolExecutionError as exc:
            return PlanStepExecutionResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status=PlanStepExecutionStatus.FAILED,
                error_message=(
                    f"tool execution raised "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if tool_result.tool_name != step.tool_name:
            return PlanStepExecutionResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status=PlanStepExecutionStatus.FAILED,
                error_message=(
                    "tool returned a mismatched tool name"
                ),
            )

        if (
            tool_result.status
            is ToolExecutionStatus.FAILED
        ):
            return PlanStepExecutionResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status=PlanStepExecutionStatus.FAILED,
                tool_result=tool_result,
                error_message=tool_result.error_message,
            )

        return PlanStepExecutionResult(
            step_id=step.step_id,
            tool_name=step.tool_name,
            status=PlanStepExecutionStatus.SUCCEEDED,
            tool_result=tool_result,
        )
