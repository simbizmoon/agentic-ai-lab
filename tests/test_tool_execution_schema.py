"""Tests for deterministic tool execution schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.tool_execution import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
)


def test_request_accepts_valid_values() -> None:
    request = ToolExecutionRequest(
        step_id="step-1",
        description="Run the test suite.",
        arguments={"path": "tests"},
    )

    assert request.step_id == "step-1"


def test_request_rejects_blank_step_id() -> None:
    with pytest.raises(
        ValidationError,
        match="step_id must not be blank",
    ):
        ToolExecutionRequest(
            step_id=" ",
            description="Run tests.",
        )


def test_success_result_accepts_output() -> None:
    result = ToolExecutionResult(
        tool_name="pytest",
        status=ToolExecutionStatus.SUCCEEDED,
        output={"passed": 10},
    )

    assert result.error_message is None


def test_failed_result_requires_error_message() -> None:
    with pytest.raises(
        ValidationError,
        match="requires an error message",
    ):
        ToolExecutionResult(
            tool_name="pytest",
            status=ToolExecutionStatus.FAILED,
        )


def test_success_result_rejects_error_message() -> None:
    with pytest.raises(
        ValidationError,
        match="must not have an error message",
    ):
        ToolExecutionResult(
            tool_name="pytest",
            status=ToolExecutionStatus.SUCCEEDED,
            error_message="unexpected",
        )
