"""Tests for named document workflow transition steps."""

import pytest

from app.schemas.document_workflow_state import (
    DocumentWorkflowState,
    DocumentWorkflowStatus,
)
from app.workflows.document_state_machine import (
    InvalidWorkflowTransitionError,
)
from app.workflows.document_workflow_steps import (
    complete_direct_response,
    complete_final_response,
    fail_document_workflow,
    mark_tool_selected,
    record_tool_observation,
    request_tool_correction,
    retry_tool_execution,
    start_model_decision,
)


def initial_state() -> DocumentWorkflowState:
    """Return a received workflow state."""

    return DocumentWorkflowState(
        status=DocumentWorkflowStatus.RECEIVED,
        user_request="Analyze the supplied document.",
    )


def test_start_model_decision() -> None:
    state = start_model_decision(initial_state())

    assert state.status == DocumentWorkflowStatus.MODEL_DECISION


def test_complete_direct_response() -> None:
    state = start_model_decision(initial_state())

    completed = complete_direct_response(
        state,
        final_answer="No Tool was required.",
    )

    assert completed.status == DocumentWorkflowStatus.COMPLETED
    assert completed.final_answer == "No Tool was required."
    assert completed.selected_tool_name is None


def test_mark_tool_selected() -> None:
    state = start_model_decision(initial_state())

    selected = mark_tool_selected(
        state,
        tool_name="get_document_statistics",
        call_id="call_123",
        arguments_json='{"document_text":"example"}',
    )

    assert (
        selected.status
        == DocumentWorkflowStatus.TOOL_EXECUTION
    )
    assert selected.selected_tool_name == (
        "get_document_statistics"
    )
    assert selected.tool_call_id == "call_123"
    assert selected.tool_arguments_json == (
        '{"document_text":"example"}'
    )


def test_request_tool_correction() -> None:
    state = start_model_decision(initial_state())
    state = mark_tool_selected(
        state,
        tool_name="get_document_statistics",
        call_id="call_invalid",
        arguments_json='{"document_text":"   "}',
    )

    correcting = request_tool_correction(state)

    assert (
        correcting.status
        == DocumentWorkflowStatus.TOOL_CORRECTION
    )
    assert correcting.correction_attempted is True


def test_retry_tool_execution() -> None:
    state = start_model_decision(initial_state())
    state = mark_tool_selected(
        state,
        tool_name="get_document_statistics",
        call_id="call_invalid",
        arguments_json='{"document_text":"   "}',
    )
    state = request_tool_correction(state)

    retried = retry_tool_execution(
        state,
        tool_name="get_document_statistics",
        call_id="call_corrected",
        arguments_json='{"document_text":"corrected"}',
    )

    assert (
        retried.status
        == DocumentWorkflowStatus.TOOL_EXECUTION
    )
    assert retried.tool_call_id == "call_corrected"
    assert retried.correction_attempted is True


def test_record_tool_observation() -> None:
    state = start_model_decision(initial_state())
    state = mark_tool_selected(
        state,
        tool_name="get_document_statistics",
        call_id="call_123",
        arguments_json='{"document_text":"example"}',
    )

    observed = record_tool_observation(
        state,
        observation={
            "character_count": 7,
            "word_count": 1,
            "line_count": 1,
        },
    )

    assert (
        observed.status
        == DocumentWorkflowStatus.FINAL_RESPONSE
    )
    assert observed.observation == {
        "character_count": 7,
        "word_count": 1,
        "line_count": 1,
    }


def test_complete_final_response() -> None:
    state = start_model_decision(initial_state())
    state = mark_tool_selected(
        state,
        tool_name="get_document_statistics",
        call_id="call_123",
        arguments_json='{"document_text":"example"}',
    )
    state = record_tool_observation(
        state,
        observation={
            "character_count": 7,
            "word_count": 1,
            "line_count": 1,
        },
    )

    completed = complete_final_response(
        state,
        final_answer="The document contains one word.",
    )

    assert completed.status == DocumentWorkflowStatus.COMPLETED
    assert completed.final_answer == (
        "The document contains one word."
    )


def test_fail_document_workflow() -> None:
    state = start_model_decision(initial_state())

    failed = fail_document_workflow(
        state,
        error_code="model_failed",
        error_message="The model request failed.",
    )

    assert failed.status == DocumentWorkflowStatus.FAILED
    assert failed.error_code == "model_failed"
    assert failed.error_message == "The model request failed."


def test_step_rejects_invalid_source_state() -> None:
    state = initial_state()

    with pytest.raises(InvalidWorkflowTransitionError):
        mark_tool_selected(
            state,
            tool_name="get_document_statistics",
            call_id="call_123",
            arguments_json='{"document_text":"example"}',
        )


def test_completed_workflow_cannot_fail() -> None:
    state = start_model_decision(initial_state())
    state = complete_direct_response(
        state,
        final_answer="Completed.",
    )

    with pytest.raises(InvalidWorkflowTransitionError):
        fail_document_workflow(
            state,
            error_code="late_failure",
            error_message="Too late.",
        )
