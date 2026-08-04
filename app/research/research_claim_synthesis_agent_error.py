"""Errors raised by claim and synthesis specialist agents."""

from __future__ import annotations


class ClaimAnalystAgentError(ValueError):
    """Raised when a claim analyst cannot execute work."""


class SynthesisSpecialistAgentError(ValueError):
    """Raised when a synthesis specialist cannot execute work."""
