"""Errors raised by application retry scheduling."""

from __future__ import annotations


class ApplicationRetrySchedulingServiceError(RuntimeError):
    """Base retry scheduling service error."""


class ApplicationJobNotRetryableError(
    ApplicationRetrySchedulingServiceError
):
    """Raised when the source job cannot be retried."""


class ApplicationRetryAlreadyScheduledError(
    ApplicationRetrySchedulingServiceError
):
    """Raised when another attempt already exists."""
