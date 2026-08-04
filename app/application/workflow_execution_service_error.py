"""Errors raised by workflow execution services."""

from __future__ import annotations


class ApplicationWorkflowExecutionServiceError(RuntimeError):
    """Base workflow execution application error."""


class ApplicationWorkflowExecutionFailedError(
    ApplicationWorkflowExecutionServiceError
):
    """Raised after a workflow failure is persisted."""

    def __init__(
        self,
        *,
        execution_id: str,
        failure_code: str,
        message: str,
    ) -> None:
        self.execution_id = execution_id
        self.failure_code = failure_code
        self.failure_message = message

        super().__init__(
            "workflow execution failed: "
            f"{execution_id}: {failure_code}: {message}"
        )
