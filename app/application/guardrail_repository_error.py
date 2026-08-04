"""Errors raised by application guardrail repositories."""

from __future__ import annotations


class ApplicationGuardrailRepositoryError(RuntimeError):
    """Base guardrail repository error."""


class ApplicationGuardrailAlreadyExistsError(
    ApplicationGuardrailRepositoryError
):
    """Raised when a guardrail evaluation already exists."""


class ApplicationGuardrailNotFoundError(
    ApplicationGuardrailRepositoryError
):
    """Raised when a guardrail evaluation cannot be found."""


class ApplicationGuardrailVersionConflictError(
    ApplicationGuardrailRepositoryError
):
    """Raised when optimistic concurrency validation fails."""
