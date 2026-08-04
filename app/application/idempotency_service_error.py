"""Errors raised by application idempotency services."""

from __future__ import annotations


class ApplicationIdempotencyServiceError(RuntimeError):
    """Base idempotency service error."""


class ApplicationIdempotencyConflictError(
    ApplicationIdempotencyServiceError
):
    """Raised when a reused key has a different request."""


class ApplicationIdempotencyInProgressError(
    ApplicationIdempotencyServiceError
):
    """Raised when the same operation is already running."""


class ApplicationIdempotencyRetryNotAllowedError(
    ApplicationIdempotencyServiceError
):
    """Raised when a failed operation cannot be restarted."""
