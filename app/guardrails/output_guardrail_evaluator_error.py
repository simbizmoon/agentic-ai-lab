"""Errors raised by output guardrail evaluation."""

from __future__ import annotations


class OutputGuardrailEvaluatorError(ValueError):
    """Raised when output guardrails cannot be evaluated."""
