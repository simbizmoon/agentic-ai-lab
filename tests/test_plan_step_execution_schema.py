"""Tests for plan step execution result schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_step_execution import (
    PlanStepExecutionResult,
    PlanStepExecutionStatus,
)
from app.schemas.tool_execution import (
    ToolExecutionResult,
    ToolExecutionStatus,
)


def successful_tool_result() -> ToolExecutionResult:
    """Return one successful tool result."""

    return ToolExecutionResult(
        tool_name="python",
        status=ToolExecutionStatus.SUCCEEDED,
        output={"value": 1},
    )


def test_success_result_requires_tool_result() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a tool result",
    ):
        PlanStepExecutionResult(
            step_id="step-1",
            tool_name="python",
            status=PlanStepExecutionStatus.SUCCEEDED,
        )


def test_success_result_accepts_matching_tool() -> None:
    result = PlanStepExecutionResult(
        step_id="step-1",
        tool_name="python",
        status=PlanStepExecutionStatus.SUCCEEDED,
        tool_result=successful_tool_result(),
    )

    assert result.error_message is None


def test_result_rejects_mismatched_tool_name() -> None:
    with pytest.raises(
        ValidationError,
        match="must match tool result",
    ):
        PlanStepExecutionResult(
            step_id="step-1",
            tool_name="pytest",
            status=PlanStepExecutionStatus.FAILED,
            tool_result=successful_tool_result(),
            error_message="Tool mismatch.",
        )


def test_unsuccessful_result_requires_error() -> None:
    with pytest.raises(
        ValidationError,
        match="requires an error message",
    ):
        PlanStepExecutionResult(
            step_id="step-1",
            tool_name="python",
            status=PlanStepExecutionStatus.FAILED,
        )
