"""Tests for integrated planning result schemas."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.created_plan import CreatedPlan
from app.schemas.plan import (
    Plan,
    PlanStep,
    PlanStepStatus,
)
from app.schemas.plan_draft import PlanStepDraft
from app.schemas.plan_validation import (
    PlanValidationResult,
)
from app.schemas.planner_client_result import (
    PlannerClientResult,
)
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import (
    PlannerOutputValidationCode,
    PlannerOutputValidationIssue,
    PlannerOutputValidationResult,
)
from app.schemas.planner_prompt import (
    PlannerPrompt,
    PlannerPromptKind,
    PlannerPromptMessage,
    PlannerPromptRole,
)
from app.schemas.planning_result import PlanningResult

NOW = datetime(
    2026,
    8,
    3,
    22,
    0,
    tzinfo=UTC,
)


def prompt() -> PlannerPrompt:
    """Return one valid planner prompt."""

    return PlannerPrompt(
        kind=PlannerPromptKind.INITIAL_PLAN,
        messages=[
            PlannerPromptMessage(
                role=PlannerPromptRole.SYSTEM,
                content="System instructions.",
            ),
            PlannerPromptMessage(
                role=PlannerPromptRole.USER,
                content="Planning request.",
            ),
        ],
        maximum_steps=3,
        available_tools=["python"],
    )


def planner_result(
    *,
    valid: bool = True,
) -> PlannerClientResult:
    """Return one planner-client result."""

    validation = (
        PlannerOutputValidationResult(
            valid=True,
            issues=[],
            execution_order=["step-1"],
        )
        if valid
        else PlannerOutputValidationResult(
            valid=False,
            issues=[
                PlannerOutputValidationIssue(
                    code=(
                        PlannerOutputValidationCode
                        .TOOL_NOT_AVAILABLE
                    ),
                    message="Tool is unavailable.",
                    step_id="step-1",
                )
            ],
            execution_order=["step-1"],
        )
    )

    return PlannerClientResult(
        output=PlanDraftOutput(
            reasoning_summary="Use one step.",
            steps=[
                PlanStepDraft(
                    step_id="step-1",
                    title="Execute",
                    description="Execute the operation.",
                    tool_name="python",
                )
            ],
        ),
        validation=validation,
    )


def created_plan(
    *,
    step_id: str = "step-1",
) -> CreatedPlan:
    """Return one created plan."""

    return CreatedPlan(
        plan=Plan(
            plan_id="plan-001",
            goal="Execute the operation.",
            steps=[
                PlanStep(
                    step_id=step_id,
                    title="Execute",
                    description="Execute the operation.",
                    status=PlanStepStatus.READY,
                    tool_name="python",
                )
            ],
            created_at=NOW,
            updated_at=NOW,
        ),
        validation=PlanValidationResult(
            valid=True,
            issues=[],
            execution_order=[step_id],
        ),
    )


def test_result_accepts_consistent_values() -> None:
    result = PlanningResult(
        prompt=prompt(),
        planner_result=planner_result(),
        created_plan=created_plan(),
    )

    assert result.created_plan.plan.plan_id == (
        "plan-001"
    )


def test_result_rejects_invalid_planner_output() -> None:
    with pytest.raises(
        ValidationError,
        match="requires valid planner output",
    ):
        PlanningResult(
            prompt=prompt(),
            planner_result=planner_result(valid=False),
            created_plan=created_plan(),
        )


def test_result_rejects_mismatched_step_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="steps must match planner output",
    ):
        PlanningResult(
            prompt=prompt(),
            planner_result=planner_result(),
            created_plan=created_plan(
                step_id="different-step"
            ),
        )
