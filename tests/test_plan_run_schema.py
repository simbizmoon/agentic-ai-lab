"""Tests for repeated structured plan execution schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_run import (
    PlanRunRequest,
    PlanRunResult,
    PlanRunStatus,
)
from app.schemas.plan_validation import (
    PlanValidationResult,
)

NOW = datetime(
    2026,
    8,
    3,
    19,
    0,
    tzinfo=UTC,
)


def plan() -> Plan:
    """Return one completed plan."""

    return Plan(
        plan_id="plan-001",
        goal="Complete one operation.",
        status=PlanStatus.COMPLETED,
        steps=[
            PlanStep(
                step_id="step-1",
                title="Execute",
                description="Execute the operation.",
                status=PlanStepStatus.COMPLETED,
                tool_name="python",
            )
        ],
        created_at=NOW,
        updated_at=NOW,
    )


def validation() -> PlanValidationResult:
    """Return one valid plan validation result."""

    return PlanValidationResult(
        valid=True,
        issues=[],
        execution_order=["step-1"],
    )


def test_request_has_safe_defaults() -> None:
    request = PlanRunRequest()

    assert request.maximum_cycles == 100
    assert request.stop_on_no_progress is True


def test_request_rejects_zero_cycles() -> None:
    with pytest.raises(ValidationError):
        PlanRunRequest(maximum_cycles=0)


def test_result_accepts_completed_plan() -> None:
    result = PlanRunResult(
        plan=plan(),
        validation=validation(),
        cycles=[],
        status=PlanRunStatus.COMPLETED,
        message="Plan completed.",
        executed_step_ids=[],
    )

    assert result.status is PlanRunStatus.COMPLETED


def test_result_rejects_blank_message() -> None:
    with pytest.raises(
        ValidationError,
        match="message must not be blank",
    ):
        PlanRunResult(
            plan=plan(),
            validation=validation(),
            cycles=[],
            status=PlanRunStatus.COMPLETED,
            message=" ",
            executed_step_ids=[],
        )


def test_result_rejects_duplicate_executed_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="executed step IDs must be unique",
    ):
        PlanRunResult(
            plan=plan(),
            validation=validation(),
            cycles=[],
            status=PlanRunStatus.COMPLETED,
            message="Plan completed.",
            executed_step_ids=[
                "step-1",
                "step-1",
            ],
        )


def test_result_rejects_unknown_executed_id() -> None:
    with pytest.raises(
        ValidationError,
        match="must reference plan steps",
    ):
        PlanRunResult(
            plan=plan(),
            validation=validation(),
            cycles=[],
            status=PlanRunStatus.COMPLETED,
            message="Plan completed.",
            executed_step_ids=["missing"],
        )
