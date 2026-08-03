"""Tests for agent plan step drafts."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_draft import PlanStepDraft


def test_draft_accepts_valid_values() -> None:
    draft = PlanStepDraft(
        step_id="step-1",
        title="Analyze the goal",
        description="Identify requirements.",
        tool_name="python",
    )

    assert draft.step_id == "step-1"
    assert draft.dependencies == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("step_id", ""),
        ("step_id", " "),
        ("title", ""),
        ("description", " "),
    ],
)
def test_draft_rejects_blank_required_text(
    field: str,
    value: str,
) -> None:
    values = {
        "step_id": "step-1",
        "title": "Analyze",
        "description": "Analyze the goal.",
    }
    values[field] = value

    with pytest.raises(
        ValidationError,
        match=f"{field} must not be blank",
    ):
        PlanStepDraft(**values)


def test_draft_rejects_duplicate_dependencies() -> None:
    with pytest.raises(
        ValidationError,
        match="dependencies must be unique",
    ):
        PlanStepDraft(
            step_id="step-2",
            title="Execute",
            description="Execute the task.",
            dependencies=[
                "step-1",
                "step-1",
            ],
        )


def test_draft_rejects_self_dependency() -> None:
    with pytest.raises(
        ValidationError,
        match="must not depend on itself",
    ):
        PlanStepDraft(
            step_id="step-1",
            title="Execute",
            description="Execute the task.",
            dependencies=["step-1"],
        )


def test_draft_rejects_blank_tool_name() -> None:
    with pytest.raises(
        ValidationError,
        match="tool_name must not be blank",
    ):
        PlanStepDraft(
            step_id="step-1",
            title="Execute",
            description="Execute the task.",
            tool_name=" ",
        )


def test_draft_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PlanStepDraft(
            step_id="step-1",
            title="Execute",
            description="Execute the task.",
            unknown_value=True,
        )
