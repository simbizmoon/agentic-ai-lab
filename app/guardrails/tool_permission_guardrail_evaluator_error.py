"""Errors raised by tool permission guardrail evaluation."""

from __future__ import annotations


class ToolPermissionGuardrailEvaluatorError(ValueError):
    """Raised when tool permissions cannot be evaluated."""
