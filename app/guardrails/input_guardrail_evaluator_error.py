"""Errors raised by input guardrail evaluation."""

from __future__ import annotations


class InputGuardrailEvaluatorError(ValueError):
    """Raised when input guardrails cannot be evaluated."""
