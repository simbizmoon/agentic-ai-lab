"""Errors raised by idempotency repositories."""

from __future__ import annotations


class ApplicationIdempotencyRepositoryError(RuntimeError):
    """Base idempotency repository error."""


class ApplicationIdempotencyAlreadyExistsError(
    ApplicationIdempotencyRepositoryError
):
    """Raised when a unique idempotency identity exists."""


class ApplicationIdempotencyNotFoundError(
    ApplicationIdempotencyRepositoryError
):
    """Raised when an idempotency record is missing."""


class ApplicationIdempotencyVersionConflictError(
    ApplicationIdempotencyRepositoryError
):
    """Raised on optimistic concurrency conflict."""
