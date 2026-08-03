"""State transition rules for the document workflow."""

from __future__ import annotations

from app.schemas.document_workflow_state import (
    DocumentWorkflowState,
    DocumentWorkflowStatus,
)


class InvalidWorkflowTransitionError(RuntimeError):
    """Raised when a document workflow transition is not allowed."""

    def __init__(
        self,
        *,
        current_status: DocumentWorkflowStatus,
        next_status: DocumentWorkflowStatus,
    ) -> None:
        message = (
            "invalid document workflow transition: "
            f"{current_status.value} -> {next_status.value}"
        )

        super().__init__(message)

        self.current_status = current_status
        self.next_status = next_status


ALLOWED_DOCUMENT_WORKFLOW_TRANSITIONS: dict[
    DocumentWorkflowStatus,
    frozenset[DocumentWorkflowStatus],
] = {
    DocumentWorkflowStatus.RECEIVED: frozenset(
        {
            DocumentWorkflowStatus.MODEL_DECISION,
            DocumentWorkflowStatus.FAILED,
        }
    ),
    DocumentWorkflowStatus.MODEL_DECISION: frozenset(
        {
            DocumentWorkflowStatus.TOOL_EXECUTION,
            DocumentWorkflowStatus.COMPLETED,
            DocumentWorkflowStatus.FAILED,
        }
    ),
    DocumentWorkflowStatus.TOOL_EXECUTION: frozenset(
        {
            DocumentWorkflowStatus.TOOL_CORRECTION,
            DocumentWorkflowStatus.FINAL_RESPONSE,
            DocumentWorkflowStatus.FAILED,
        }
    ),
    DocumentWorkflowStatus.TOOL_CORRECTION: frozenset(
        {
            DocumentWorkflowStatus.TOOL_EXECUTION,
            DocumentWorkflowStatus.FAILED,
        }
    ),
    DocumentWorkflowStatus.FINAL_RESPONSE: frozenset(
        {
            DocumentWorkflowStatus.COMPLETED,
            DocumentWorkflowStatus.FAILED,
        }
    ),
    DocumentWorkflowStatus.COMPLETED: frozenset(),
    DocumentWorkflowStatus.FAILED: frozenset(),
}


def is_document_workflow_transition_allowed(
    *,
    current_status: DocumentWorkflowStatus,
    next_status: DocumentWorkflowStatus,
) -> bool:
    """Return whether one document workflow transition is allowed."""

    allowed_next_statuses = (
        ALLOWED_DOCUMENT_WORKFLOW_TRANSITIONS[current_status]
    )

    return next_status in allowed_next_statuses


def transition_document_workflow(
    state: DocumentWorkflowState,
    *,
    next_status: DocumentWorkflowStatus,
    updates: dict[str, object] | None = None,
) -> DocumentWorkflowState:
    """Return a validated state after one allowed transition."""

    if not is_document_workflow_transition_allowed(
        current_status=state.status,
        next_status=next_status,
    ):
        raise InvalidWorkflowTransitionError(
            current_status=state.status,
            next_status=next_status,
        )

    update_values: dict[str, object] = {
        "status": next_status,
    }

    if updates is not None:
        if "status" in updates:
            raise ValueError(
                "status must be supplied through next_status"
            )

        update_values.update(updates)

    return state.model_copy(
        update=update_values,
        deep=True,
    )
