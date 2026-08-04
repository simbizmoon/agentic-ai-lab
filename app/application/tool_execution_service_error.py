"""Errors raised by tool execution application services."""

from __future__ import annotations


class ApplicationToolExecutionServiceError(RuntimeError):
    """Base tool execution application error."""


class ApplicationToolExecutionFailedError(
    ApplicationToolExecutionServiceError
):
    """Raised after a tool execution failure is persisted."""

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
            "tool execution failed: "
            f"{execution_id}: {failure_code}: {message}"
        )
