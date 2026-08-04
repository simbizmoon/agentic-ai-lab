"""Errors raised by the application job queue service."""

from __future__ import annotations


class ApplicationJobQueueServiceError(RuntimeError):
    """Base application job queue service error."""


class ApplicationJobNotQueueableError(
    ApplicationJobQueueServiceError
):
    """Raised when a job cannot enter the queue."""


class ApplicationJobLeaseOwnershipError(
    ApplicationJobQueueServiceError
):
    """Raised when a worker does not own a job lease."""


class ApplicationJobLeaseExpiredError(
    ApplicationJobQueueServiceError
):
    """Raised when a worker lease has expired."""
