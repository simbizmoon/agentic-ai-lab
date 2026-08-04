"""Errors raised by cancellation request repositories."""

from __future__ import annotations


class ApplicationCancellationRepositoryError(RuntimeError):
    """Base cancellation repository error."""


class ApplicationCancellationAlreadyExistsError(
    ApplicationCancellationRepositoryError
):
    """Raised when a cancellation request ID exists."""


class ApplicationCancellationNotFoundError(
    ApplicationCancellationRepositoryError
):
    """Raised when a cancellation request is missing."""


class ApplicationCancellationVersionConflictError(
    ApplicationCancellationRepositoryError
):
    """Raised when optimistic concurrency validation fails."""
