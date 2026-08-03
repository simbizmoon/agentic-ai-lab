"""Tests for document workflow transition rules."""

import pytest

from app.schemas.document_workflow_state import (
    DocumentWorkflowState,
    DocumentWorkflowStatus,
)
from app.workflows.document_state_machine import (
    ALLOWED_DOCUMENT_WORKFLOW_TRANSITIONS,
    InvalidWorkflowTransitionError,
    is_document_workflow_transition_allowed,
    transition_document_workflow,
)


def received_state() -> DocumentWorkflowState:
    """Return a valid initial workflow state."""

    return DocumentWorkflowState(
        status=DocumentWorkflowStatus.RECEIVED,
        user_request="Analyze the supplied document.",
    )


def test_received_can_transition_to_model_decision() -> None:
    assert is_document_workflow_transition_allowed(
        current_status=DocumentWorkflowStatus.RECEIVED,
        next_status=DocumentWorkflowStatus.MODEL_DECISION,
    )


def test_received_can_transition_to_failed() -> None:
    assert is_document_workflow_transition_allowed(
        current_status=DocumentWorkflowStatus.RECEIVED,
        next_status=DocumentWorkflowStatus.FAILED,
    )


def test_received_cannot_transition_directly_to_completed() -> None:
    assert not is_document_workflow_transition_allowed(
        current_status=DocumentWorkflowStatus.RECEIVED,
        next_status=DocumentWorkflowStatus.COMPLETED,
    )


def test_tool_correction_can_retry_tool_execution() -> None:
    assert is_document_workflow_transition_allowed(
        current_status=DocumentWorkflowStatus.TOOL_CORRECTION,
        next_status=DocumentWorkflowStatus.TOOL_EXECUTION,
    )


def test_terminal_states_have_no_outgoing_transitions() -> None:
    assert (
        ALLOWED_DOCUMENT_WORKFLOW_TRANSITIONS[
            DocumentWorkflowStatus.COMPLETED
        ]
        == frozenset()
    )
    assert (
        ALLOWED_DOCUMENT_WORKFLOW_TRANSITIONS[
            DocumentWorkflowStatus.FAILED
        ]
        == frozenset()
    )


def test_transition_returns_new_state() -> None:
    original = received_state()

    transitioned = transition_document_workflow(
        original,
        next_status=DocumentWorkflowStatus.MODEL_DECISION,
    )

    assert original.status == DocumentWorkflowStatus.RECEIVED
    assert (
        transitioned.status
        == DocumentWorkflowStatus.MODEL_DECISION
    )
    assert transitioned is not original


def test_transition_applies_state_updates() -> None:
    state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.MODEL_DECISION,
        user_request="Count the document.",
    )

    transitioned = transition_document_workflow(
        state,
        next_status=DocumentWorkflowStatus.TOOL_EXECUTION,
        updates={
            "selected_tool_name": "get_document_statistics",
            "tool_call_id": "call_123",
            "tool_arguments_json": (
                '{"document_text":"example"}'
            ),
        },
    )

    assert (
        transitioned.status
        == DocumentWorkflowStatus.TOOL_EXECUTION
    )
    assert transitioned.selected_tool_name == (
        "get_document_statistics"
    )
    assert transitioned.tool_call_id == "call_123"


def test_transition_rejects_invalid_transition() -> None:
    state = received_state()

    with pytest.raises(
        InvalidWorkflowTransitionError,
        match="received -> completed",
    ) as exc_info:
        transition_document_workflow(
            state,
            next_status=DocumentWorkflowStatus.COMPLETED,
        )

    assert (
        exc_info.value.current_status
        == DocumentWorkflowStatus.RECEIVED
    )
    assert (
        exc_info.value.next_status
        == DocumentWorkflowStatus.COMPLETED
    )


def test_transition_rejects_status_in_updates() -> None:
    state = received_state()

    with pytest.raises(
        ValueError,
        match="status must be supplied through next_status",
    ):
        transition_document_workflow(
            state,
            next_status=DocumentWorkflowStatus.MODEL_DECISION,
            updates={
                "status": DocumentWorkflowStatus.FAILED,
            },
        )


def test_completed_state_cannot_transition() -> None:
    state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.COMPLETED,
        user_request="Explain the document.",
        final_answer="Completed.",
    )

    with pytest.raises(InvalidWorkflowTransitionError):
        transition_document_workflow(
            state,
            next_status=DocumentWorkflowStatus.MODEL_DECISION,
        )


def test_failed_state_cannot_transition() -> None:
    state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.FAILED,
        user_request="Explain the document.",
        error_code="workflow_failed",
        error_message="The workflow failed.",
    )

    with pytest.raises(InvalidWorkflowTransitionError):
        transition_document_workflow(
            state,
            next_status=DocumentWorkflowStatus.RECEIVED,
        )
