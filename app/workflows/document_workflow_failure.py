"""Structured failure information for document workflows."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.document_workflow_state import (
    DocumentWorkflowState,
    DocumentWorkflowStatus,
)
from app.workflows.document_workflow_steps import (
    fail_document_workflow,
)


@dataclass(frozen=True)
class DocumentWorkflowFailure:
    """A failed workflow state and its safe error information."""

    state: DocumentWorkflowState
    error_code: str
    safe_message: str

    def __post_init__(self) -> None:
        """Validate consistency between the state and error fields."""

        if self.state.status != DocumentWorkflowStatus.FAILED:
            raise ValueError(
                "DocumentWorkflowFailure requires FAILED state"
            )

        if self.state.error_code != self.error_code:
            raise ValueError(
                "failure error_code must match state error_code"
            )

        if self.state.error_message != self.safe_message:
            raise ValueError(
                "failure message must match state error_message"
            )


def create_document_workflow_failure(
    state: DocumentWorkflowState,
    *,
    error_code: str,
    safe_message: str,
) -> DocumentWorkflowFailure:
    """Transition a nonterminal state to FAILED and preserve details."""

    failed_state = fail_document_workflow(
        state,
        error_code=error_code,
        error_message=safe_message,
        events=state.events,
    )

    return DocumentWorkflowFailure(
        state=failed_state,
        error_code=error_code,
        safe_message=safe_message,
    )
