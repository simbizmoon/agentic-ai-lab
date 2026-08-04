"""Errors raised by retry policy evaluation."""

from __future__ import annotations


class RetryPolicyEvaluatorError(ValueError):
    """Raised when a retry decision cannot be generated."""
