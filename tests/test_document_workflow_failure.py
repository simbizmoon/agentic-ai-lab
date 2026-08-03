"""Tests for structured document workflow failures."""

import pytest

from app.schemas.document_workflow_state import (
    DocumentWorkflowState,
    DocumentWorkflowStatus,
)
from app.workflows.document_state_machine import (
    InvalidWorkflowTransitionError,
)
from app.workflows.document_workflow_failure import (
    DocumentWorkflowFailure,
    create_document_workflow_failure,
)
from app.workflows.document_workflow_steps import (
    start_model_decision,
)


def model_decision_state() -> DocumentWorkflowState:
    """Return a workflow in model-decision state."""

    state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.RECEIVED,
        user_request="Analyze the document.",
    )

    return start_model_decision(state)


def test_create_failure_transitions_state_to_failed() -> None:
    failure = create_document_workflow_failure(
        model_decision_state(),
        error_code="model_failed",
        safe_message="The model request failed.",
    )

    assert failure.state.status == DocumentWorkflowStatus.FAILED
    assert failure.state.error_code == "model_failed"
    assert failure.state.error_message == (
        "The model request failed."
    )
    assert failure.error_code == "model_failed"
    assert failure.safe_message == "The model request failed."


def test_failure_preserves_user_request() -> None:
    state = model_decision_state()

    failure = create_document_workflow_failure(
        state,
        error_code="invalid_response",
        safe_message="The response was invalid.",
    )

    assert failure.state.user_request == state.user_request


def test_failure_preserves_existing_events() -> None:
    state = model_decision_state()

    failure = create_document_workflow_failure(
        state,
        error_code="tool_failed",
        safe_message="The Tool failed.",
    )

    assert failure.state.events == state.events


def test_failure_rejects_nonfailed_state() -> None:
    state = model_decision_state()

    with pytest.raises(
        ValueError,
        match="requires FAILED state",
    ):
        DocumentWorkflowFailure(
            state=state,
            error_code="model_failed",
            safe_message="The model request failed.",
        )


def test_failure_rejects_mismatched_error_code() -> None:
    failed_state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.FAILED,
        user_request="Analyze the document.",
        error_code="actual_code",
        error_message="The request failed.",
    )

    with pytest.raises(
        ValueError,
        match="error_code must match",
    ):
        DocumentWorkflowFailure(
            state=failed_state,
            error_code="different_code",
            safe_message="The request failed.",
        )


def test_failure_rejects_mismatched_message() -> None:
    failed_state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.FAILED,
        user_request="Analyze the document.",
        error_code="workflow_failed",
        error_message="Actual safe message.",
    )

    with pytest.raises(
        ValueError,
        match="message must match",
    ):
        DocumentWorkflowFailure(
            state=failed_state,
            error_code="workflow_failed",
            safe_message="Different safe message.",
        )


def test_terminal_state_cannot_be_failed_again() -> None:
    failed_state = DocumentWorkflowState(
        status=DocumentWorkflowStatus.FAILED,
        user_request="Analyze the document.",
        error_code="first_failure",
        error_message="Already failed.",
    )

    with pytest.raises(InvalidWorkflowTransitionError):
        create_document_workflow_failure(
            failed_state,
            error_code="second_failure",
            safe_message="Failed again.",
        )
