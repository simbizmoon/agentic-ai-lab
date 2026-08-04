"""Schemas for timeout and cancellation evaluation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.guardrails.execution_timeout_policy import (
    ExecutionSubjectType,
)


class ExecutionLifecycleStatus(StrEnum):
    """Current execution lifecycle status."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class CancellationMode(StrEnum):
    """Requested cancellation behavior."""

    GRACEFUL = "graceful"
    FORCE = "force"


class ExecutionControlDecisionType(StrEnum):
    """Decision produced by execution control evaluation."""

    CONTINUE = "continue"
    WARN = "warn"
    REQUEST_CANCELLATION = "request_cancellation"
    FORCE_CANCEL = "force_cancel"
    TIMEOUT = "timeout"
    TERMINAL = "terminal"


class ExecutionControlReason(StrEnum):
    """Reason for one execution control decision."""

    WITHIN_LIMITS = "within_limits"
    SOFT_TIMEOUT_EXCEEDED = "soft_timeout_exceeded"
    HARD_TIMEOUT_EXCEEDED = "hard_timeout_exceeded"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    GRACEFUL_CANCELLATION_REQUESTED = (
        "graceful_cancellation_requested"
    )
    FORCE_CANCELLATION_REQUESTED = (
        "force_cancellation_requested"
    )
    CANCELLATION_GRACE_PERIOD_EXCEEDED = (
        "cancellation_grace_period_exceeded"
    )
    EXECUTION_ALREADY_TERMINAL = "execution_already_terminal"


class CancellationRequest(BaseModel):
    """One explicit execution cancellation request."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    cancellation_id: str
    requested_at: datetime
    requested_by: str
    reason: str
    mode: CancellationMode = CancellationMode.GRACEFUL
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate cancellation request values."""

        required_text = {
            "cancellation_id": self.cancellation_id,
            "requested_by": self.requested_by,
            "reason": self.reason,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if self.requested_at.tzinfo is None:
            raise ValueError(
                "requested_at must be timezone-aware"
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


class ExecutionRuntimeSnapshot(BaseModel):
    """Runtime state supplied to timeout evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    subject_id: str
    subject_type: ExecutionSubjectType
    status: ExecutionLifecycleStatus
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    deadline_at: datetime | None = None
    cancellation_request: CancellationRequest | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate runtime timestamp ordering."""

        if not self.execution_id.strip():
            raise ValueError(
                "execution_id must not be blank"
            )

        if not self.subject_id.strip():
            raise ValueError(
                "subject_id must not be blank"
            )

        timestamps = {
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "deadline_at": self.deadline_at,
        }

        for field_name, value in timestamps.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        if (
            self.started_at is not None
            and self.started_at < self.created_at
        ):
            raise ValueError(
                "started_at must not precede created_at"
            )

        if (
            self.finished_at is not None
            and self.started_at is None
        ):
            raise ValueError(
                "finished_at requires started_at"
            )

        if (
            self.finished_at is not None
            and self.started_at is not None
            and self.finished_at < self.started_at
        ):
            raise ValueError(
                "finished_at must not precede started_at"
            )

        terminal_statuses = {
            ExecutionLifecycleStatus.COMPLETED,
            ExecutionLifecycleStatus.FAILED,
            ExecutionLifecycleStatus.CANCELLED,
            ExecutionLifecycleStatus.TIMED_OUT,
        }

        if (
            self.status in terminal_statuses
            and self.finished_at is None
        ):
            raise ValueError(
                "terminal execution requires finished_at"
            )

        if (
            self.status not in terminal_statuses
            and self.finished_at is not None
        ):
            raise ValueError(
                "nonterminal execution must not include "
                "finished_at"
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


class ExecutionControlDecision(BaseModel):
    """Complete timeout and cancellation decision."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    decision_id: str
    policy_id: str
    execution_id: str
    decision: ExecutionControlDecisionType
    reason: ExecutionControlReason
    elapsed_seconds: float = Field(ge=0)
    remaining_soft_seconds: float | None = None
    remaining_hard_seconds: float | None = None
    remaining_deadline_seconds: float | None = None
    cancellation_grace_remaining_seconds: float | None = None
    should_stop: bool
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        """Validate control-decision consistency."""

        required_text = {
            "decision_id": self.decision_id,
            "policy_id": self.policy_id,
            "execution_id": self.execution_id,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        stopping_decisions = {
            ExecutionControlDecisionType.FORCE_CANCEL,
            ExecutionControlDecisionType.TIMEOUT,
            ExecutionControlDecisionType.TERMINAL,
        }

        if self.should_stop != (
            self.decision in stopping_decisions
        ):
            raise ValueError(
                "should_stop must match the decision type"
            )

        return self
