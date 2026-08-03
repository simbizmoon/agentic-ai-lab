"""Tests for Tool workflow event schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.tool_workflow_event import (
    ToolWorkflowEvent,
    ToolWorkflowEventType,
)


def test_request_received_event() -> None:
    event = ToolWorkflowEvent(
        event_type=ToolWorkflowEventType.REQUEST_RECEIVED,
        details={"request_length": 25},
    )

    assert event.model_dump(mode="json") == {
        "event_type": "request_received",
        "tool_name": None,
        "details": {
            "request_length": 25,
        },
    }


def test_tool_selected_event_requires_tool_name() -> None:
    event = ToolWorkflowEvent(
        event_type=ToolWorkflowEventType.TOOL_SELECTED,
        tool_name="get_document_statistics",
    )

    assert event.tool_name == "get_document_statistics"


@pytest.mark.parametrize(
    "event_type",
    [
        ToolWorkflowEventType.TOOL_SELECTED,
        ToolWorkflowEventType.TOOL_EXECUTION_SUCCEEDED,
        ToolWorkflowEventType.TOOL_ARGUMENT_CORRECTION_REQUESTED,
        ToolWorkflowEventType.TOOL_ARGUMENTS_CORRECTED,
    ],
)
def test_tool_specific_events_reject_missing_tool_name(
    event_type: ToolWorkflowEventType,
) -> None:
    with pytest.raises(
        ValidationError,
        match="tool_name is required",
    ):
        ToolWorkflowEvent(event_type=event_type)


@pytest.mark.parametrize(
    "event_type",
    [
        ToolWorkflowEventType.REQUEST_RECEIVED,
        ToolWorkflowEventType.DIRECT_RESPONSE,
        ToolWorkflowEventType.FINAL_RESPONSE_CREATED,
    ],
)
def test_non_tool_events_reject_tool_name(
    event_type: ToolWorkflowEventType,
) -> None:
    with pytest.raises(
        ValidationError,
        match="tool_name is not allowed",
    ):
        ToolWorkflowEvent(
            event_type=event_type,
            tool_name="unexpected_tool",
        )


def test_event_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ToolWorkflowEvent.model_validate(
            {
                "event_type": "request_received",
                "details": {},
                "unexpected": True,
            }
        )


def test_event_type_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        ToolWorkflowEvent.model_validate(
            {
                "event_type": "unknown_event",
                "details": {},
            }
        )
