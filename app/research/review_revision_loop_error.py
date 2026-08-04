"""Errors raised by the deterministic review and revision loop."""

from __future__ import annotations


class ReviewRevisionLoopError(ValueError):
    """Raised when a review and revision loop is misconfigured."""
