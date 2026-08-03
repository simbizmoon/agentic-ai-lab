"""Tests for agent plan creation requests."""

import pytest
from pydantic import ValidationError

from app.schemas.plan_request import (
    PlanCreationRequest,
)


def test_request_accepts_valid_values() -> None:
    request = PlanCreationRequest(
        goal="Build and validate a planning agent.",
        constraints=[
            "Use deterministic validation.",
            "Run all tests.",
        ],
        available_tools=[
            "python",
            "pytest",
        ],
        maximum_steps=8,
    )

    assert request.maximum_steps == 8
    assert request.allow_parallel_steps is True


@pytest.mark.parametrize(
    "goal",
    ["", " ", "\n\t"],
)
def test_request_rejects_blank_goal(
    goal: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match="plan goal must not be blank",
    ):
        PlanCreationRequest(goal=goal)


def test_request_rejects_blank_constraint() -> None:
    with pytest.raises(
        ValidationError,
        match="constraints must not contain blank",
    ):
        PlanCreationRequest(
            goal="Build the planner.",
            constraints=["valid", " "],
        )


def test_request_rejects_duplicate_constraints() -> None:
    with pytest.raises(
        ValidationError,
        match="constraints must be unique",
    ):
        PlanCreationRequest(
            goal="Build the planner.",
            constraints=[
                "Run tests",
                "run tests",
            ],
        )


def test_request_rejects_duplicate_tools() -> None:
    with pytest.raises(
        ValidationError,
        match="available_tools must be unique",
    ):
        PlanCreationRequest(
            goal="Build the planner.",
            available_tools=[
                "Python",
                "python",
            ],
        )


def test_request_rejects_invalid_maximum_steps() -> None:
    with pytest.raises(ValidationError):
        PlanCreationRequest(
            goal="Build the planner.",
            maximum_steps=0,
        )


def test_request_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        PlanCreationRequest(
            goal="Build the planner.",
            unknown_value=True,
        )
