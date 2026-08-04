"""Errors raised by research execution application services."""

from __future__ import annotations


class ApplicationResearchExecutionServiceError(RuntimeError):
    """Base research execution application error."""


class ApplicationResearchExecutionFailedError(
    ApplicationResearchExecutionServiceError
):
    """Raised after a research runner fails."""

    def __init__(
        self,
        *,
        execution_id: str,
        message: str,
    ) -> None:
        self.execution_id = execution_id
        self.failure_message = message

        super().__init__(
            "research execution failed: "
            f"{execution_id}: {message}"
        )
