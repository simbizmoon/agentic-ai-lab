"""Tests for deterministic replanning schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_evaluation import (
    PlanEvaluationCode,
    PlanEvaluationDecision,
)
from app.schemas.replan import (
    ReplanRequest,
    ReplanStepSummary,
)


def summary(
    *,
    step_id: str = "step-1",
    status: str = "failed",
) -> ReplanStepSummary:
    """Return one valid replan step summary."""

    return ReplanStepSummary(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete {step_id}.",
        status=status,
        tool_name="python",
    )


def request(
    **overrides: object,
) -> ReplanRequest:
    """Return one valid replan request."""

    values: dict[str, object] = {
        "original_plan_id": "plan-001",
        "goal": "Complete the requested work.",
        "evaluation_decision": (
            PlanEvaluationDecision.REPLAN_REQUIRED
        ),
        "evaluation_codes": [
            PlanEvaluationCode.STEP_EXECUTION_FAILED
        ],
        "evaluation_summary": "One step failed.",
        "failed_steps": [summary()],
        "constraints": ["Run tests."],
        "available_tools": ["python"],
        "maximum_steps": 5,
        "previous_cycle_count": 1,
    }
    values.update(overrides)

    return ReplanRequest(**values)


def test_request_accepts_valid_context() -> None:
    value = request()

    assert value.original_plan_id == "plan-001"
    assert len(value.failed_steps) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("original_plan_id", ""),
        ("goal", " "),
        ("evaluation_summary", "\n"),
    ],
)
def test_request_rejects_blank_required_text(
    field: str,
    value: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=f"{field} must not be blank",
    ):
        request(**{field: value})


def test_request_rejects_duplicate_codes() -> None:
    with pytest.raises(
        ValidationError,
        match="evaluation codes must be unique",
    ):
        request(
            evaluation_codes=[
                PlanEvaluationCode.STEP_EXECUTION_FAILED,
                PlanEvaluationCode.STEP_EXECUTION_FAILED,
            ]
        )


def test_request_rejects_overlapping_steps() -> None:
    duplicate = summary()

    with pytest.raises(
        ValidationError,
        match="step summaries must not overlap",
    ):
        request(
            completed_steps=[duplicate],
            failed_steps=[duplicate],
        )


def test_request_rejects_duplicate_constraints() -> None:
    with pytest.raises(
        ValidationError,
        match="constraints must be unique",
    ):
        request(
            constraints=[
                "Run tests",
                "run tests",
            ]
        )


def test_step_summary_rejects_blank_status() -> None:
    with pytest.raises(
        ValidationError,
        match="status must not be blank",
    ):
        summary(status=" ")


def test_step_summary_rejects_duplicate_dependencies() -> None:
    with pytest.raises(
        ValidationError,
        match="dependencies must be unique",
    ):
        ReplanStepSummary(
            step_id="step-2",
            title="Execute step-2",
            description="Complete step-2.",
            status="pending",
            dependencies=[
                "step-1",
                "step-1",
            ],
        )
