"""Schemas for deterministic guardrail evaluation results."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.guardrails.guardrail_policy import (
    GuardrailAction,
    GuardrailScope,
    GuardrailSeverity,
)


class GuardrailDecision(StrEnum):
    """Final decision from one guardrail evaluation."""

    ALLOWED = "allowed"
    WARNED = "warned"
    BLOCKED = "blocked"


class GuardrailViolation(BaseModel):
    """One violation detected by a guardrail evaluator."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    violation_id: str
    policy_id: str
    rule_id: str
    code: str
    scope: GuardrailScope
    severity: GuardrailSeverity
    action: GuardrailAction
    message: str
    blocking: bool
    retryable: bool = False
    field_path: str | None = None
    remediation: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_violation(self) -> Self:
        """Validate violation identity and action semantics."""

        required_text = {
            "violation_id": self.violation_id,
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
            "code": self.code,
            "message": self.message,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.field_path is not None
            and not self.field_path.strip()
        ):
            raise ValueError(
                "field_path must not be blank when provided"
            )

        if (
            self.remediation is not None
            and not self.remediation.strip()
        ):
            raise ValueError(
                "remediation must not be blank when provided"
            )

        nonblocking_actions = {
            GuardrailAction.ALLOW,
            GuardrailAction.LOG,
            GuardrailAction.WARN,
        }

        if self.blocking and self.action in nonblocking_actions:
            raise ValueError(
                "blocking violation requires a blocking action"
            )

        if (
            self.action is GuardrailAction.RETRY
            and not self.retryable
        ):
            raise ValueError(
                "retry violation must be retryable"
            )

        return self


class GuardrailEvaluationResult(BaseModel):
    """Complete result from one guardrail evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evaluation_id: str
    subject_id: str
    scope: GuardrailScope
    decision: GuardrailDecision
    violations: list[GuardrailViolation] = Field(
        default_factory=list
    )
    evaluated_policy_ids: list[str] = Field(
        default_factory=list
    )
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate decision and violation consistency."""

        required_text = {
            "evaluation_id": self.evaluation_id,
            "subject_id": self.subject_id,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_unique_text(
            self.evaluated_policy_ids,
            field_name="evaluated_policy_ids",
        )

        violation_ids = [
            violation.violation_id.strip().casefold()
            for violation in self.violations
        ]

        if len(set(violation_ids)) != len(violation_ids):
            raise ValueError(
                "violations must have unique violation IDs"
            )

        blocking_violations = [
            violation
            for violation in self.violations
            if violation.blocking
        ]

        if (
            self.decision is GuardrailDecision.ALLOWED
            and self.violations
        ):
            raise ValueError(
                "allowed result must not contain violations"
            )

        if (
            self.decision is GuardrailDecision.WARNED
            and (
                not self.violations
                or blocking_violations
            )
        ):
            raise ValueError(
                "warned result requires only nonblocking "
                "violations"
            )

        if (
            self.decision is GuardrailDecision.BLOCKED
            and not blocking_violations
        ):
            raise ValueError(
                "blocked result requires a blocking violation"
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

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique nonblank strings."""

        if any(not value.strip() for value in values):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )

    @property
    def allowed(self) -> bool:
        """Return whether execution may proceed."""

        return self.decision in {
            GuardrailDecision.ALLOWED,
            GuardrailDecision.WARNED,
        }

    @property
    def blocking_violations(
        self,
    ) -> list[GuardrailViolation]:
        """Return blocking violations."""

        return [
            violation
            for violation in self.violations
            if violation.blocking
        ]
