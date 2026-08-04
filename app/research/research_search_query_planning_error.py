"""Errors raised during research search query planning."""

from __future__ import annotations


class ResearchSearchQueryPlanningError(ValueError):
    """Raised when no safe search plan can be created."""
