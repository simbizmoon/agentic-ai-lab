"""Tests for planner output validation schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.planner_output_validation import (
    PlannerOutputValidationCode,
    PlannerOutputValidationIssue,
    PlannerOutputValidationResult,
)


def issue() -> PlannerOutputValidationIssue:
    """Return one validation issue."""

    return PlannerOutputValidationIssue(
        code=(
            PlannerOutputValidationCode
            .TOO_MANY_STEPS
        ),
        message="Too many steps.",
    )


def test_invalid_result_accepts_issue() -> None:
    result = PlannerOutputValidationResult(
        valid=False,
        issues=[issue()],
        execution_order=[],
    )

    assert result.valid is False


def test_valid_result_accepts_execution_order() -> None:
    result = PlannerOutputValidationResult(
        valid=True,
        issues=[],
        execution_order=["step-1"],
    )

    assert result.valid is True


def test_valid_result_rejects_issue() -> None:
    with pytest.raises(
        ValidationError,
        match="valid flag is inconsistent",
    ):
        PlannerOutputValidationResult(
            valid=True,
            issues=[issue()],
            execution_order=[],
        )


def test_invalid_result_requires_issue() -> None:
    with pytest.raises(
        ValidationError,
        match="valid flag is inconsistent",
    ):
        PlannerOutputValidationResult(
            valid=False,
            issues=[],
            execution_order=[],
        )


def test_result_rejects_duplicate_execution_order() -> None:
    with pytest.raises(
        ValidationError,
        match="execution order must contain unique",
    ):
        PlannerOutputValidationResult(
            valid=True,
            issues=[],
            execution_order=[
                "step-1",
                "step-1",
            ],
        )
