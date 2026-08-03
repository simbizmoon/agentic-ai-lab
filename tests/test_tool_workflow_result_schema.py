"""Tests for the structured Tool workflow result."""

import pytest
from pydantic import ValidationError

from app.schemas.tool_workflow_result import ToolWorkflowResult


def test_tool_workflow_result_with_observation() -> None:
    result = ToolWorkflowResult(
        tool_used=True,
        tool_name="get_document_statistics",
        observation={
            "character_count": 377,
            "word_count": 77,
            "line_count": 11,
        },
        final_answer=(
            "The document has 377 characters, "
            "77 words, and 11 lines."
        ),
    )

    assert result.tool_used is True
    assert result.tool_name == "get_document_statistics"
    assert result.observation == {
        "character_count": 377,
        "word_count": 77,
        "line_count": 11,
    }


def test_tool_workflow_result_without_tool() -> None:
    result = ToolWorkflowResult(
        tool_used=False,
        final_answer="A Tool was not needed.",
    )

    assert result.tool_used is False
    assert result.tool_name is None
    assert result.observation is None


def test_tool_used_requires_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolWorkflowResult(
            tool_used=True,
            observation={"value": 1},
            final_answer="Result",
        )


def test_tool_used_requires_observation() -> None:
    with pytest.raises(ValidationError):
        ToolWorkflowResult(
            tool_used=True,
            tool_name="get_document_statistics",
            final_answer="Result",
        )


def test_tool_not_used_rejects_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolWorkflowResult(
            tool_used=False,
            tool_name="get_document_statistics",
            final_answer="Result",
        )


def test_tool_not_used_rejects_observation() -> None:
    with pytest.raises(ValidationError):
        ToolWorkflowResult(
            tool_used=False,
            observation={"value": 1},
            final_answer="Result",
        )


def test_tool_workflow_result_rejects_empty_final_answer() -> None:
    with pytest.raises(ValidationError):
        ToolWorkflowResult(
            tool_used=False,
            final_answer="",
        )


def test_tool_workflow_result_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ToolWorkflowResult(
            tool_used=False,
            final_answer="Result",
            unsupported=True,
        )


def test_workflow_result_accepts_structured_events() -> None:
    from app.schemas.tool_workflow_event import (
        ToolWorkflowEvent,
        ToolWorkflowEventType,
    )

    result = ToolWorkflowResult(
        tool_used=True,
        tool_name="get_document_statistics",
        observation={
            "character_count": 10,
            "word_count": 2,
            "line_count": 1,
        },
        final_answer="The document has two words.",
        events=[
            ToolWorkflowEvent(
                event_type=(
                    ToolWorkflowEventType.REQUEST_RECEIVED
                ),
                details={"request_length": 20},
            ),
            ToolWorkflowEvent(
                event_type=(
                    ToolWorkflowEventType.TOOL_SELECTED
                ),
                tool_name="get_document_statistics",
            ),
        ],
    )

    assert len(result.events) == 2
    assert result.events[0].event_type.value == (
        "request_received"
    )
    assert result.events[1].tool_name == (
        "get_document_statistics"
    )


def test_workflow_result_uses_independent_event_lists() -> None:
    first = ToolWorkflowResult(
        tool_used=False,
        final_answer="First answer.",
    )
    second = ToolWorkflowResult(
        tool_used=False,
        final_answer="Second answer.",
    )

    assert first.events == []
    assert second.events == []
    assert first.events is not second.events
