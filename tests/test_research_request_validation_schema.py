"""Tests for research request validation schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.research_request_validation import (
    ResearchRequestValidationCode,
    ResearchRequestValidationIssue,
    ResearchRequestValidationResult,
    ResearchRequestValidationSeverity,
)


def issue(
    *,
    severity: ResearchRequestValidationSeverity,
) -> ResearchRequestValidationIssue:
    """Return one validation issue."""

    return ResearchRequestValidationIssue(
        code=(
            ResearchRequestValidationCode
            .QUESTION_TOO_SHORT
        ),
        severity=severity,
        field="question",
        message="Research question is too short.",
    )


def test_result_accepts_consistent_counts() -> None:
    result = ResearchRequestValidationResult(
        request_id="research-001",
        valid=False,
        issues=[
            issue(
                severity=(
                    ResearchRequestValidationSeverity.ERROR
                )
            )
        ],
        error_count=1,
        warning_count=0,
    )

    assert result.valid is False
    assert result.error_count == 1


def test_result_accepts_warning_only_result() -> None:
    result = ResearchRequestValidationResult(
        request_id="research-001",
        valid=True,
        issues=[
            issue(
                severity=(
                    ResearchRequestValidationSeverity.WARNING
                )
            )
        ],
        error_count=0,
        warning_count=1,
    )

    assert result.valid is True


def test_result_rejects_incorrect_error_count() -> None:
    with pytest.raises(
        ValidationError,
        match="error_count must match",
    ):
        ResearchRequestValidationResult(
            request_id="research-001",
            valid=False,
            issues=[
                issue(
                    severity=(
                        ResearchRequestValidationSeverity.ERROR
                    )
                )
            ],
            error_count=0,
            warning_count=0,
        )


def test_result_rejects_incorrect_warning_count() -> None:
    with pytest.raises(
        ValidationError,
        match="warning_count must match",
    ):
        ResearchRequestValidationResult(
            request_id="research-001",
            valid=True,
            issues=[
                issue(
                    severity=(
                        ResearchRequestValidationSeverity.WARNING
                    )
                )
            ],
            error_count=0,
            warning_count=0,
        )


def test_result_rejects_invalid_valid_flag() -> None:
    with pytest.raises(
        ValidationError,
        match="valid must be true exactly",
    ):
        ResearchRequestValidationResult(
            request_id="research-001",
            valid=True,
            issues=[
                issue(
                    severity=(
                        ResearchRequestValidationSeverity.ERROR
                    )
                )
            ],
            error_count=1,
            warning_count=0,
        )


def test_result_rejects_duplicate_issues() -> None:
    duplicate = issue(
        severity=ResearchRequestValidationSeverity.ERROR
    )

    with pytest.raises(
        ValidationError,
        match="must not contain duplicates",
    ):
        ResearchRequestValidationResult(
            request_id="research-001",
            valid=False,
            issues=[duplicate, duplicate],
            error_count=2,
            warning_count=0,
        )
