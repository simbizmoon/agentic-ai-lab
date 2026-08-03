"""Tests for agent plan lifecycle result schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.plan import (
    Plan,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_lifecycle import (
    PlanLifecycleResult,
)
from app.schemas.plan_validation import (
    PlanValidationResult,
)

NOW = datetime(
    2026,
    8,
    3,
    16,
    0,
    tzinfo=UTC,
)


def plan() -> Plan:
    """Return one valid plan."""

    return Plan(
        plan_id="plan-001",
        goal="Build a planning agent.",
        steps=[
            PlanStep(
                step_id="step-1",
                title="Analyze",
                description="Analyze the goal.",
                status=PlanStepStatus.READY,
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


def test_result_accepts_known_changed_step() -> None:
    result = PlanLifecycleResult(
        plan=plan(),
        validation=validation(),
        changed_step_ids=["step-1"],
    )

    assert result.changed_step_ids == ["step-1"]


def test_result_rejects_duplicate_changed_steps() -> None:
    with pytest.raises(
        ValidationError,
        match="changed step IDs must be unique",
    ):
        PlanLifecycleResult(
            plan=plan(),
            validation=validation(),
            changed_step_ids=[
                "step-1",
                "step-1",
            ],
        )


def test_result_rejects_unknown_changed_step() -> None:
    with pytest.raises(
        ValidationError,
        match="must reference steps in the plan",
    ):
        PlanLifecycleResult(
            plan=plan(),
            validation=validation(),
            changed_step_ids=["missing"],
        )
