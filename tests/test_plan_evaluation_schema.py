"""Tests for deterministic plan evaluation schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_evaluation import (
    PlanEvaluationCode,
    PlanEvaluationDecision,
    PlanEvaluationResult,
)


def valid_result(
    **overrides: object,
) -> PlanEvaluationResult:
    """Return one valid evaluation result."""

    values: dict[str, object] = {
        "decision": (
            PlanEvaluationDecision.GOAL_ACHIEVED
        ),
        "codes": [
            PlanEvaluationCode.PLAN_COMPLETED
        ],
        "summary": "The plan completed.",
        "failed_step_ids": [],
        "incomplete_step_ids": [],
        "replan_recommended": False,
        "human_review_recommended": False,
    }
    values.update(overrides)

    return PlanEvaluationResult(**values)


def test_result_accepts_goal_achieved() -> None:
    result = valid_result()

    assert result.decision is (
        PlanEvaluationDecision.GOAL_ACHIEVED
    )


def test_result_rejects_blank_summary() -> None:
    with pytest.raises(
        ValidationError,
        match="summary must not be blank",
    ):
        valid_result(summary=" ")


def test_result_rejects_duplicate_codes() -> None:
    with pytest.raises(
        ValidationError,
        match="codes must be unique",
    ):
        valid_result(
            codes=[
                PlanEvaluationCode.PLAN_COMPLETED,
                PlanEvaluationCode.PLAN_COMPLETED,
            ]
        )


def test_replan_decision_requires_recommendation() -> None:
    with pytest.raises(
        ValidationError,
        match="must recommend replanning",
    ):
        valid_result(
            decision=(
                PlanEvaluationDecision
                .REPLAN_REQUIRED
            ),
            codes=[
                PlanEvaluationCode.NO_EXECUTABLE_STEP
            ],
            incomplete_step_ids=["step-1"],
            replan_recommended=False,
        )


def test_human_review_decision_requires_recommendation() -> None:
    with pytest.raises(
        ValidationError,
        match="must recommend human review",
    ):
        valid_result(
            decision=(
                PlanEvaluationDecision
                .HUMAN_REVIEW_REQUIRED
            ),
            codes=[
                PlanEvaluationCode
                .PLAN_VALIDATION_FAILED
            ],
            incomplete_step_ids=["step-1"],
            human_review_recommended=False,
        )


def test_goal_achieved_rejects_incomplete_steps() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain unfinished work",
    ):
        valid_result(
            incomplete_step_ids=["step-1"]
        )


def test_result_rejects_duplicate_failed_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="failed step IDs must be unique",
    ):
        valid_result(
            decision=(
                PlanEvaluationDecision
                .REPLAN_REQUIRED
            ),
            codes=[
                PlanEvaluationCode
                .STEP_EXECUTION_FAILED
            ],
            failed_step_ids=[
                "step-1",
                "step-1",
            ],
            incomplete_step_ids=["step-1"],
            replan_recommended=True,
        )
