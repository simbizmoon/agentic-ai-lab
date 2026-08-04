"""Errors raised by the deterministic source reader specialist."""

from __future__ import annotations


class SourceReaderSpecialistAgentError(ValueError):
    """Raised when a source reader cannot execute an assignment."""
