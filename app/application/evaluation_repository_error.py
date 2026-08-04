"""Errors raised by application evaluation repositories."""

from __future__ import annotations


class ApplicationEvaluationRepositoryError(RuntimeError):
    """Base evaluation repository error."""


class ApplicationEvaluationAlreadyExistsError(
    ApplicationEvaluationRepositoryError
):
    """Raised when an evaluation ID already exists."""


class ApplicationEvaluationNotFoundError(
    ApplicationEvaluationRepositoryError
):
    """Raised when an evaluation record cannot be found."""


class ApplicationEvaluationVersionConflictError(
    ApplicationEvaluationRepositoryError
):
    """Raised when optimistic concurrency validation fails."""
