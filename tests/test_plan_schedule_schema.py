"""Tests for deterministic plan scheduling schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_schedule import (
    PlanScheduleReason,
    PlanScheduleRequest,
    PlanScheduleResult,
)


def test_request_has_safe_defaults() -> None:
    request = PlanScheduleRequest()

    assert request.allow_parallel_steps is True
    assert request.maximum_selected_steps == 1
    assert request.allow_new_steps_while_active is False


def test_request_rejects_zero_selection_limit() -> None:
    with pytest.raises(ValidationError):
        PlanScheduleRequest(
            maximum_selected_steps=0
        )


def test_result_accepts_selected_ready_steps() -> None:
    result = PlanScheduleResult(
        selected_step_ids=[
            "step-1",
            "step-2",
        ],
        ready_step_ids=[
            "step-1",
            "step-2",
            "step-3",
        ],
        active_step_ids=[],
        reason=PlanScheduleReason.STEPS_SELECTED,
    )

    assert result.selected_step_ids == [
        "step-1",
        "step-2",
    ]


def test_result_rejects_selected_non_ready_step() -> None:
    with pytest.raises(
        ValidationError,
        match="selected step IDs must be ready",
    ):
        PlanScheduleResult(
            selected_step_ids=["step-2"],
            ready_step_ids=["step-1"],
            active_step_ids=[],
            reason=PlanScheduleReason.STEPS_SELECTED,
        )


def test_selected_reason_requires_selected_steps() -> None:
    with pytest.raises(
        ValidationError,
        match="requires selected steps",
    ):
        PlanScheduleResult(
            selected_step_ids=[],
            ready_step_ids=["step-1"],
            active_step_ids=[],
            reason=PlanScheduleReason.STEPS_SELECTED,
        )


def test_non_selection_reason_rejects_selection() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain selected steps",
    ):
        PlanScheduleResult(
            selected_step_ids=["step-1"],
            ready_step_ids=["step-1"],
            active_step_ids=[],
            reason=PlanScheduleReason.NO_READY_STEPS,
        )


def test_result_rejects_duplicate_ready_steps() -> None:
    with pytest.raises(
        ValidationError,
        match="ready step IDs must be unique",
    ):
        PlanScheduleResult(
            selected_step_ids=[],
            ready_step_ids=[
                "step-1",
                "step-1",
            ],
            active_step_ids=[],
            reason=PlanScheduleReason.PLAN_INVALID,
        )


def test_result_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PlanScheduleResult(
            selected_step_ids=[],
            ready_step_ids=[],
            active_step_ids=[],
            reason=PlanScheduleReason.NO_READY_STEPS,
            unknown_value=True,
        )
