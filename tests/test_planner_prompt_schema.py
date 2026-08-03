"""Tests for structured planner prompt schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.planner_prompt import (
    PlannerPrompt,
    PlannerPromptKind,
    PlannerPromptMessage,
    PlannerPromptRole,
)


def messages() -> list[PlannerPromptMessage]:
    """Return one valid planner message pair."""

    return [
        PlannerPromptMessage(
            role=PlannerPromptRole.SYSTEM,
            content="Trusted planner instructions.",
        ),
        PlannerPromptMessage(
            role=PlannerPromptRole.USER,
            content="<planning_request>{}</planning_request>",
        ),
    ]


def test_initial_prompt_accepts_valid_messages() -> None:
    prompt = PlannerPrompt(
        kind=PlannerPromptKind.INITIAL_PLAN,
        messages=messages(),
        maximum_steps=5,
        available_tools=["python"],
    )

    assert prompt.source_plan_id is None


def test_replan_prompt_requires_source_plan_id() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a source plan ID",
    ):
        PlannerPrompt(
            kind=PlannerPromptKind.REPLAN,
            messages=messages(),
            maximum_steps=5,
            available_tools=["python"],
        )


def test_initial_prompt_rejects_source_plan_id() -> None:
    with pytest.raises(
        ValidationError,
        match="must not have a source plan ID",
    ):
        PlannerPrompt(
            kind=PlannerPromptKind.INITIAL_PLAN,
            messages=messages(),
            maximum_steps=5,
            available_tools=["python"],
            source_plan_id="plan-001",
        )


def test_prompt_requires_system_then_user_order() -> None:
    reversed_messages = list(reversed(messages()))

    with pytest.raises(
        ValidationError,
        match="system then user",
    ):
        PlannerPrompt(
            kind=PlannerPromptKind.INITIAL_PLAN,
            messages=reversed_messages,
            maximum_steps=5,
        )


def test_prompt_rejects_duplicate_tools() -> None:
    with pytest.raises(
        ValidationError,
        match="available tools must be unique",
    ):
        PlannerPrompt(
            kind=PlannerPromptKind.INITIAL_PLAN,
            messages=messages(),
            maximum_steps=5,
            available_tools=[
                "Python",
                "python",
            ],
        )


def test_message_rejects_blank_content() -> None:
    with pytest.raises(
        ValidationError,
        match="content must not be blank",
    ):
        PlannerPromptMessage(
            role=PlannerPromptRole.SYSTEM,
            content=" ",
        )
