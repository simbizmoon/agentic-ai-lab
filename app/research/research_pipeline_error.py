"""Errors raised by the single research-agent pipeline."""

from __future__ import annotations


class ResearchPipelineError(ValueError):
    """Raised when a research pipeline stage cannot continue."""
