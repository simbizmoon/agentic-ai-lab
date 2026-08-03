"""Tests for structured planner output schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_draft import PlanStepDraft
from app.schemas.planner_output import PlanDraftOutput


def step(
    *,
    step_id: str,
    dependencies: list[str] | None = None,
) -> PlanStepDraft:
    """Return one planner-generated step."""

    return PlanStepDraft(
        step_id=step_id,
        title=f"Execute {step_id}",
        description=f"Complete {step_id}.",
        dependencies=dependencies or [],
    )


def test_output_accepts_valid_linear_steps() -> None:
    output = PlanDraftOutput(
        reasoning_summary="A linear plan is sufficient.",
        steps=[
            step(step_id="step-1"),
            step(
                step_id="step-2",
                dependencies=["step-1"],
            ),
        ],
    )

    assert len(output.steps) == 2


def test_output_rejects_blank_reasoning_summary() -> None:
    with pytest.raises(
        ValidationError,
        match="reasoning summary must not be blank",
    ):
        PlanDraftOutput(
            reasoning_summary=" ",
            steps=[step(step_id="step-1")],
        )


def test_output_rejects_duplicate_step_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="step IDs must be unique",
    ):
        PlanDraftOutput(
            reasoning_summary="Duplicate IDs.",
            steps=[
                step(step_id="step-1"),
                step(step_id="step-1"),
            ],
        )


def test_output_rejects_unknown_dependency() -> None:
    with pytest.raises(
        ValidationError,
        match="dependencies must reference",
    ):
        PlanDraftOutput(
            reasoning_summary="Invalid dependency.",
            steps=[
                step(
                    step_id="step-1",
                    dependencies=["missing"],
                )
            ],
        )


def test_output_rejects_duplicate_assumptions() -> None:
    with pytest.raises(
        ValidationError,
        match="assumptions must be unique",
    ):
        PlanDraftOutput(
            reasoning_summary="Assumptions are needed.",
            steps=[step(step_id="step-1")],
            assumptions=[
                "Tests are available",
                "tests are available",
            ],
        )


def test_output_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PlanDraftOutput(
            reasoning_summary="Valid plan.",
            steps=[step(step_id="step-1")],
            unknown_value=True,
        )
