"""Errors raised during research task decomposition."""

from __future__ import annotations

from app.schemas.research_request_validation import (
    ResearchRequestValidationResult,
)


class ResearchTaskDecompositionError(ValueError):
    """Raised when a request cannot be decomposed safely."""

    def __init__(
        self,
        validation: ResearchRequestValidationResult,
    ) -> None:
        self.validation = validation

        codes = ", ".join(
            issue.code.value
            for issue in validation.issues
            if issue.severity.value == "error"
        )

        message = "research request is not ready"

        if codes:
            message = f"{message}: {codes}"

        super().__init__(message)
