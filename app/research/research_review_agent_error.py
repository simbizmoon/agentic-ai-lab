"""Errors raised by deterministic research review agents."""

from __future__ import annotations


class SourceCriticAgentError(ValueError):
    """Raised when a source critic cannot execute an assignment."""


class CitationVerifierAgentError(ValueError):
    """Raised when a citation verifier cannot execute an assignment."""
