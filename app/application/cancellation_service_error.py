"""Errors raised by cancellation persistence services."""

from __future__ import annotations


class ApplicationCancellationServiceError(RuntimeError):
    """Base cancellation service error."""


class ApplicationCancellationAlreadyActiveError(
    ApplicationCancellationServiceError
):
    """Raised when a job already has an active request."""


class ApplicationJobCannotBeCancelledError(
    ApplicationCancellationServiceError
):
    """Raised when the target job cannot be cancelled."""


class ApplicationCancellationStateError(
    ApplicationCancellationServiceError
):
    """Raised when cancellation state is incompatible."""
