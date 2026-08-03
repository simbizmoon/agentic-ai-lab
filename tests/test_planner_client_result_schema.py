"""Tests for structured planner client results."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_draft import PlanStepDraft
from app.schemas.planner_client_result import (
    PlannerClientResult,
)
from app.schemas.planner_output import PlanDraftOutput
from app.schemas.planner_output_validation import (
    PlannerOutputValidationResult,
)


def output() -> PlanDraftOutput:
    """Return one valid planner output."""

    return PlanDraftOutput(
        reasoning_summary="Use one deterministic step.",
        steps=[
            PlanStepDraft(
                step_id="step-1",
                title="Run tests",
                description="Run the complete test suite.",
                tool_name="pytest",
            )
        ],
    )


def validation() -> PlannerOutputValidationResult:
    """Return one valid output validation."""

    return PlannerOutputValidationResult(
        valid=True,
        issues=[],
        execution_order=["step-1"],
    )


def test_result_accepts_response_metadata() -> None:
    result = PlannerClientResult(
        output=output(),
        validation=validation(),
        response_id="resp-001",
        model="gpt-5-mini",
    )

    assert result.response_id == "resp-001"


def test_result_rejects_blank_response_id() -> None:
    with pytest.raises(
        ValidationError,
        match="response_id must not be blank",
    ):
        PlannerClientResult(
            output=output(),
            validation=validation(),
            response_id=" ",
        )
