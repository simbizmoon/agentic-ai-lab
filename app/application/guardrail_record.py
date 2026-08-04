"""Persistent application guardrail result schemas."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)


class ApplicationGuardrailScope(StrEnum):
    """Persistent guardrail evaluation scope."""

    INPUT = "input"
    OUTPUT = "output"
    TOOL = "tool"
    ASSIGNMENT = "assignment"
    AGENT = "agent"
    WORKFLOW = "workflow"
    EVALUATION = "evaluation"


class ApplicationGuardrailDecision(StrEnum):
    """Persistent guardrail decision."""

    ALLOWED = "allowed"
    WARNED = "warned"
    BLOCKED = "blocked"


class ApplicationGuardrailSeverity(StrEnum):
    """Normalized violation severity."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApplicationGuardrailViolationRecord(BaseModel):
    """Persistent normalized guardrail violation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    violation_id: str
    policy_id: str
    code: str
    message: str
    severity: ApplicationGuardrailSeverity
    blocking: bool
    retryable: bool = False
    remediation: str | None = None
    reference_ids: list[str] = Field(default_factory=list)
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_violation(self) -> Self:
        """Validate persistent violation fields."""

        required_text = {
            "violation_id": self.violation_id,
            "policy_id": self.policy_id,
            "code": self.code,
            "message": self.message,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.remediation is not None
            and not self.remediation.strip()
        ):
            raise ValueError(
                "remediation must not be blank when provided"
            )

        if any(
            not reference_id.strip()
            for reference_id in self.reference_ids
        ):
            raise ValueError(
                "reference_ids must not contain blank values"
            )

        normalized = [
            reference_id.strip().casefold()
            for reference_id in self.reference_ids
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "reference_ids must not contain duplicates"
            )

        return self


class ApplicationGuardrailRecord(BaseModel):
    """Persistent application-level guardrail evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    guardrail_evaluation_id: str
    scope: ApplicationGuardrailScope
    evaluator_name: str
    evaluator_version: str

    request_id: str
    workspace_id: str
    execution_id: str | None = None
    assignment_id: str | None = None
    agent_id: str | None = None
    target_id: str
    target_type: str

    decision: ApplicationGuardrailDecision
    violations: list[
        ApplicationGuardrailViolationRecord
    ] = Field(default_factory=list)

    total_violation_count: int = Field(ge=0)
    blocking_violation_count: int = Field(ge=0)
    warning_violation_count: int = Field(ge=0)

    result_payload: dict[str, JsonValue] = Field(
        default_factory=dict
    )

    evaluated_at: datetime
    record_version: int = Field(default=1, ge=1)
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate persistent guardrail invariants."""

        required_text = {
            "guardrail_evaluation_id": (
                self.guardrail_evaluation_id
            ),
            "evaluator_name": self.evaluator_name,
            "evaluator_version": self.evaluator_version,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        optional_text = {
            "execution_id": self.execution_id,
            "assignment_id": self.assignment_id,
            "agent_id": self.agent_id,
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        if self.evaluated_at.tzinfo is None:
            raise ValueError(
                "evaluated_at must be timezone-aware"
            )

        violation_ids = [
            violation.violation_id.strip().casefold()
            for violation in self.violations
        ]

        if len(set(violation_ids)) != len(violation_ids):
            raise ValueError(
                "violations must have unique violation IDs"
            )

        actual_total = len(self.violations)
        actual_blocking = sum(
            violation.blocking
            for violation in self.violations
        )
        actual_warning = actual_total - actual_blocking

        if self.total_violation_count != actual_total:
            raise ValueError(
                "total_violation_count must equal "
                "the number of violations"
            )

        if self.blocking_violation_count != actual_blocking:
            raise ValueError(
                "blocking_violation_count must equal "
                "the number of blocking violations"
            )

        if self.warning_violation_count != actual_warning:
            raise ValueError(
                "warning_violation_count must equal "
                "the number of nonblocking violations"
            )

        if (
            self.decision is ApplicationGuardrailDecision.ALLOWED
            and self.violations
        ):
            raise ValueError(
                "allowed decision must not include violations"
            )

        if (
            self.decision is ApplicationGuardrailDecision.WARNED
            and (
                not self.violations
                or self.blocking_violation_count > 0
            )
        ):
            raise ValueError(
                "warned decision requires only nonblocking "
                "violations"
            )

        if (
            self.decision is ApplicationGuardrailDecision.BLOCKED
            and self.blocking_violation_count == 0
        ):
            raise ValueError(
                "blocked decision requires a blocking violation"
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

    @property
    def allowed(self) -> bool:
        """Return whether execution may continue."""

        return self.decision is not (
            ApplicationGuardrailDecision.BLOCKED
        )

    @property
    def blocking_violations(
        self,
    ) -> list[ApplicationGuardrailViolationRecord]:
        """Return blocking violations."""

        return [
            violation
            for violation in self.violations
            if violation.blocking
        ]
