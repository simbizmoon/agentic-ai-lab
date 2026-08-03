"""Tests for end-to-end plan execution schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_execution import (
    PlanExecutionResult,
    PlanExecutionStatus,
)
from app.schemas.plan_schedule import (
    PlanScheduleReason,
    PlanScheduleResult,
)
from app.schemas.plan_step_execution import (
    PlanStepExecutionResult,
    PlanStepExecutionStatus,
)
from app.schemas.plan_validation import (
    PlanValidationResult,
)

NOW = datetime(
    2026,
    8,
    3,
    18,
    0,
    tzinfo=UTC,
)


def plan() -> Plan:
    """Return one valid plan."""

    return Plan(
        plan_id="plan-001",
        goal="Execute a planning step.",
        status=PlanStatus.IN_PROGRESS,
        steps=[
            PlanStep(
                step_id="step-1",
                title="Execute",
                description="Execute the operation.",
                status=PlanStepStatus.READY,
                tool_name="python",
            )
        ],
        created_at=NOW,
        updated_at=NOW,
    )


def validation() -> PlanValidationResult:
    """Return one valid validation result."""

    return PlanValidationResult(
        valid=True,
        issues=[],
        execution_order=["step-1"],
    )


def schedule(
    *,
    selected: bool,
) -> PlanScheduleResult:
    """Return one schedule result."""

    return PlanScheduleResult(
        selected_step_ids=(
            ["step-1"] if selected else []
        ),
        ready_step_ids=["step-1"],
        active_step_ids=[],
        reason=(
            PlanScheduleReason.STEPS_SELECTED
            if selected
            else PlanScheduleReason.NO_READY_STEPS
        ),
    )


def step_result() -> PlanStepExecutionResult:
    """Return one unsuccessful normalized step result."""

    return PlanStepExecutionResult(
        step_id="step-1",
        tool_name="python",
        status=PlanStepExecutionStatus.FAILED,
        error_message="Execution failed.",
    )


def test_nothing_scheduled_accepts_empty_results() -> None:
    result = PlanExecutionResult(
        plan=plan(),
        validation=validation(),
        schedule=schedule(selected=False),
        step_results=[],
        status=PlanExecutionStatus.NOTHING_SCHEDULED,
    )

    assert result.step_results == []


def test_nothing_scheduled_rejects_step_results() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain step results",
    ):
        PlanExecutionResult(
            plan=plan(),
            validation=validation(),
            schedule=schedule(selected=False),
            step_results=[step_result()],
            status=PlanExecutionStatus.NOTHING_SCHEDULED,
        )


def test_step_status_requires_results() -> None:
    with pytest.raises(
        ValidationError,
        match="requires step results",
    ):
        PlanExecutionResult(
            plan=plan(),
            validation=validation(),
            schedule=schedule(selected=True),
            step_results=[],
            status=PlanExecutionStatus.STEP_FAILED,
        )


def test_result_rejects_duplicate_step_results() -> None:
    with pytest.raises(
        ValidationError,
        match="unique step IDs",
    ):
        PlanExecutionResult(
            plan=plan(),
            validation=validation(),
            schedule=schedule(selected=True),
            step_results=[
                step_result(),
                step_result(),
            ],
            status=PlanExecutionStatus.STEP_FAILED,
        )
