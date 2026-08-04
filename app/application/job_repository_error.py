"""Errors raised by application job repositories."""

from __future__ import annotations


class ApplicationJobRepositoryError(RuntimeError):
    """Base application job repository error."""


class ApplicationJobAlreadyExistsError(
    ApplicationJobRepositoryError
):
    """Raised when a job ID already exists."""


class ApplicationJobNotFoundError(
    ApplicationJobRepositoryError
):
    """Raised when a job record cannot be found."""


class ApplicationJobVersionConflictError(
    ApplicationJobRepositoryError
):
    """Raised when optimistic concurrency validation fails."""
