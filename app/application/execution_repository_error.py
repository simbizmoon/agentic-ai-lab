"""Errors raised by application execution repositories."""

from __future__ import annotations


class ApplicationExecutionRepositoryError(RuntimeError):
    """Base execution repository error."""


class ApplicationExecutionAlreadyExistsError(
    ApplicationExecutionRepositoryError
):
    """Raised when an execution ID already exists."""


class ApplicationExecutionNotFoundError(
    ApplicationExecutionRepositoryError
):
    """Raised when an execution record cannot be found."""


class ApplicationExecutionVersionConflictError(
    ApplicationExecutionRepositoryError
):
    """Raised when optimistic concurrency validation fails."""
