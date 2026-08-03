"""Tests for the document workflow state model."""

import pytest
from pydantic import ValidationError

from app.schemas.document_workflow_state import (
    DocumentWorkflowState,
    DocumentWorkflowStatus,
)


def test_received_state_contains_user_request() -> None:
    state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.RECEIVED,
        user_request="Analyze this document.",
    )

    assert state.status == DocumentWorkflowStatus.RECEIVED
    assert state.user_request == "Analyze this document."
    assert state.selected_tool_name is None
    assert state.observation is None
    assert state.final_answer is None
    assert state.events == []


def test_tool_execution_state_accepts_tool_metadata() -> None:
    state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.TOOL_EXECUTION,
        user_request="Count this document.",
        selected_tool_name="get_document_statistics",
        tool_call_id="call_123",
        tool_arguments_json=(
            '{"document_text":"example text"}'
        ),
    )

    assert state.selected_tool_name == (
        "get_document_statistics"
    )
    assert state.tool_call_id == "call_123"


def test_completed_state_requires_final_answer() -> None:
    with pytest.raises(
        ValidationError,
        match="completed workflow requires final_answer",
    ):
        DocumentWorkflowState(
            status=DocumentWorkflowStatus.COMPLETED,
            user_request="Analyze this document.",
        )


def test_completed_state_rejects_error_information() -> None:
    with pytest.raises(
        ValidationError,
        match="must not contain error_code",
    ):
        DocumentWorkflowState(
            status=DocumentWorkflowStatus.COMPLETED,
            user_request="Analyze this document.",
            final_answer="Analysis complete.",
            error_code="unexpected_error",
        )


def test_failed_state_requires_error_code() -> None:
    with pytest.raises(
        ValidationError,
        match="failed workflow requires error_code",
    ):
        DocumentWorkflowState(
            status=DocumentWorkflowStatus.FAILED,
            user_request="Analyze this document.",
            error_message="Something failed.",
        )


def test_failed_state_requires_error_message() -> None:
    with pytest.raises(
        ValidationError,
        match="failed workflow requires error_message",
    ):
        DocumentWorkflowState(
            status=DocumentWorkflowStatus.FAILED,
            user_request="Analyze this document.",
            error_code="tool_failed",
        )


def test_observation_requires_selected_tool() -> None:
    with pytest.raises(
        ValidationError,
        match="observation requires selected_tool_name",
    ):
        DocumentWorkflowState(
            status=DocumentWorkflowStatus.FINAL_RESPONSE,
            user_request="Analyze this document.",
            observation={"value": 1},
        )


def test_tool_call_id_requires_selected_tool() -> None:
    with pytest.raises(
        ValidationError,
        match="tool_call_id requires selected_tool_name",
    ):
        DocumentWorkflowState(
            status=DocumentWorkflowStatus.TOOL_EXECUTION,
            user_request="Analyze this document.",
            tool_call_id="call_123",
        )


def test_state_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        DocumentWorkflowState.model_validate(
            {
                "status": "received",
                "user_request": "Analyze this document.",
                "unexpected": True,
            }
        )


def test_state_rejects_unknown_status() -> None:
    with pytest.raises(ValidationError):
        DocumentWorkflowState.model_validate(
            {
                "status": "unknown",
                "user_request": "Analyze this document.",
            }
        )


def test_event_lists_are_independent() -> None:
    first = DocumentWorkflowState(
        status=DocumentWorkflowStatus.RECEIVED,
        user_request="First request.",
    )
    second = DocumentWorkflowState(
        status=DocumentWorkflowStatus.RECEIVED,
        user_request="Second request.",
    )

    assert first.events is not second.events
