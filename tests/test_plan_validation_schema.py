"""Tests for deterministic plan validation schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_validation import (
    PlanValidationCode,
    PlanValidationIssue,
    PlanValidationResult,
    PlanValidationSeverity,
)


def issue(
    *,
    severity: PlanValidationSeverity = (
        PlanValidationSeverity.ERROR
    ),
) -> PlanValidationIssue:
    """Return one valid validation issue."""

    return PlanValidationIssue(
        code=PlanValidationCode.CIRCULAR_DEPENDENCY,
        severity=severity,
        message="The plan contains a cycle.",
        related_step_ids=["step-1", "step-2"],
    )


def test_invalid_result_accepts_error() -> None:
    result = PlanValidationResult(
        valid=False,
        issues=[issue()],
        execution_order=[],
    )

    assert result.valid is False


def test_valid_result_accepts_warnings() -> None:
    result = PlanValidationResult(
        valid=True,
        issues=[
            issue(
                severity=(
                    PlanValidationSeverity.WARNING
                )
            )
        ],
        execution_order=["step-1"],
    )

    assert result.valid is True


def test_result_rejects_valid_flag_with_error() -> None:
    with pytest.raises(
        ValidationError,
        match="valid flag is inconsistent",
    ):
        PlanValidationResult(
            valid=True,
            issues=[issue()],
            execution_order=[],
        )


def test_result_rejects_invalid_flag_without_error() -> None:
    with pytest.raises(
        ValidationError,
        match="valid flag is inconsistent",
    ):
        PlanValidationResult(
            valid=False,
            issues=[],
            execution_order=["step-1"],
        )


def test_issue_rejects_blank_message() -> None:
    with pytest.raises(
        ValidationError,
        match="message must not be blank",
    ):
        PlanValidationIssue(
            code=(
                PlanValidationCode
                .CIRCULAR_DEPENDENCY
            ),
            severity=(
                PlanValidationSeverity.ERROR
            ),
            message=" ",
        )


def test_result_rejects_duplicate_execution_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="execution order must contain unique",
    ):
        PlanValidationResult(
            valid=True,
            issues=[],
            execution_order=[
                "step-1",
                "step-1",
            ],
        )
