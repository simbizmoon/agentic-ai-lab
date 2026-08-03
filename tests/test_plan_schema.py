"""Tests for structured agent plan schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.plan import (
    Plan,
    PlanStatus,
    PlanStep,
    PlanStepStatus,
)

NOW = datetime(
    2026,
    8,
    3,
    13,
    0,
    tzinfo=UTC,
)


def step(
    *,
    step_id: str = "step-1",
    dependencies: list[str] | None = None,
    status: PlanStepStatus = PlanStepStatus.PENDING,
) -> PlanStep:
    """Return one valid plan step."""

    return PlanStep(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete work for {step_id}.",
        dependencies=dependencies or [],
        status=status,
    )


def plan(
    *,
    steps: list[PlanStep] | None = None,
) -> Plan:
    """Return one valid structured plan."""

    return Plan(
        plan_id="plan-001",
        goal="Build and validate a planning agent.",
        status=PlanStatus.DRAFT,
        steps=steps or [step()],
        created_at=NOW,
        updated_at=NOW,
    )


def test_plan_accepts_valid_single_step() -> None:
    value = plan()

    assert value.plan_id == "plan-001"
    assert value.status is PlanStatus.DRAFT
    assert len(value.steps) == 1


def test_plan_accepts_valid_dependencies() -> None:
    value = plan(
        steps=[
            step(step_id="step-1"),
            step(
                step_id="step-2",
                dependencies=["step-1"],
            ),
        ]
    )

    assert value.steps[1].dependencies == [
        "step-1"
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("step_id", ""),
        ("step_id", " "),
        ("title", ""),
        ("description", " "),
    ],
)
def test_step_rejects_blank_required_text(
    field: str,
    value: str,
) -> None:
    values = {
        "step_id": "step-1",
        "title": "Do work",
        "description": "Complete the work.",
    }
    values[field] = value

    with pytest.raises(
        ValidationError,
        match=f"{field} must not be blank",
    ):
        PlanStep(**values)


def test_step_rejects_duplicate_dependencies() -> None:
    with pytest.raises(
        ValidationError,
        match="dependencies must be unique",
    ):
        step(
            step_id="step-2",
            dependencies=[
                "step-1",
                "step-1",
            ],
        )


def test_step_rejects_self_dependency() -> None:
    with pytest.raises(
        ValidationError,
        match="must not depend on itself",
    ):
        step(
            step_id="step-1",
            dependencies=["step-1"],
        )


def test_plan_rejects_duplicate_step_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="step IDs must be unique",
    ):
        plan(
            steps=[
                step(step_id="step-1"),
                step(step_id="step-1"),
            ]
        )


def test_plan_rejects_unknown_dependency() -> None:
    with pytest.raises(
        ValidationError,
        match="dependencies must reference",
    ):
        plan(
            steps=[
                step(
                    step_id="step-1",
                    dependencies=["missing-step"],
                )
            ]
        )


def test_plan_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValidationError,
        match="created_at must be timezone-aware",
    ):
        Plan(
            plan_id="plan-001",
            goal="Build the planner.",
            steps=[step()],
            created_at=NOW.replace(tzinfo=None),
            updated_at=NOW,
        )


def test_plan_rejects_updated_at_before_created_at() -> None:
    with pytest.raises(
        ValidationError,
        match="must not be earlier",
    ):
        Plan(
            plan_id="plan-001",
            goal="Build the planner.",
            steps=[step()],
            created_at=NOW,
            updated_at=NOW.replace(
                hour=12
            ),
        )


def test_plan_requires_at_least_one_step() -> None:
    with pytest.raises(ValidationError):
        Plan(
            plan_id="plan-001",
            goal="Build the planner.",
            steps=[],
            created_at=NOW,
            updated_at=NOW,
        )


def test_plan_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        Plan(
            plan_id="plan-001",
            goal="Build the planner.",
            steps=[step()],
            created_at=NOW,
            updated_at=NOW,
            unknown_value=True,
        )
