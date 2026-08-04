"""Schemas for the Phase 11 end-to-end reliability evaluation."""

from __future__ import annotations

from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.guardrails.failure_recovery import (
    FailureRecoveryDecision,
)
from app.guardrails.guardrail_result import (
    GuardrailEvaluationResult,
)
from app.guardrails.reliability_metrics import (
    ReliabilityMetrics,
)
from app.guardrails.retry_decision import RetryDecision


class Phase11E2EResult(BaseModel):
    """Complete Phase 11 guardrail and reliability result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_id: str
    input_guardrail_result: GuardrailEvaluationResult
    denied_tool_guardrail_result: GuardrailEvaluationResult
    allowed_tool_guardrail_result: GuardrailEvaluationResult
    retry_decisions: list[RetryDecision] = Field(
        min_length=1
    )
    recovery_decision: FailureRecoveryDecision
    reliability_metrics: ReliabilityMetrics
    completed: bool
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate E2E result consistency."""

        if not self.evaluation_id.strip():
            raise ValueError(
                "evaluation_id must not be blank"
            )

        if not self.summary.strip():
            raise ValueError(
                "summary must not be blank"
            )

        if not self.input_guardrail_result.allowed:
            raise ValueError(
                "E2E result requires allowed input guardrail"
            )

        if self.denied_tool_guardrail_result.allowed:
            raise ValueError(
                "E2E result requires denied tool call"
            )

        if not self.allowed_tool_guardrail_result.allowed:
            raise ValueError(
                "E2E result requires allowed tool call"
            )

        if not self.completed:
            raise ValueError(
                "Phase 11 E2E result must be completed"
            )

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

        return self
