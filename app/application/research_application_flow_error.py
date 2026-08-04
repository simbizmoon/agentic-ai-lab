"""Errors raised by the research application flow."""

from __future__ import annotations


class ApplicationResearchFlowError(RuntimeError):
    """Base research application flow error."""


class ApplicationResearchFlowStateError(
    ApplicationResearchFlowError
):
    """Raised when persisted flow state is invalid."""
