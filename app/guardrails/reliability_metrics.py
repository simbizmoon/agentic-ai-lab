"""Schemas for deterministic reliability metrics."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.guardrails.retry_policy import RetryFailureCategory


class ReliabilityExecutionStatus(StrEnum):
    """Normalized execution status used for reliability metrics."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ReliabilityRecoveryStatus(StrEnum):
    """Recovery outcome associated with one execution."""

    NOT_ATTEMPTED = "not_attempted"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class ReliabilityExecutionRecord(BaseModel):
    """One normalized execution record."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    status: ReliabilityExecutionStatus
    duration_seconds: float = Field(ge=0)
    attempt_count: int = Field(default=1, ge=1)
    guardrail_evaluated: bool = False
    guardrail_blocked: bool = False
    recovery_status: ReliabilityRecoveryStatus = (
        ReliabilityRecoveryStatus.NOT_ATTEMPTED
    )
    failure_category: RetryFailureCategory | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate execution-record consistency."""

        if not self.execution_id.strip():
            raise ValueError(
                "execution_id must not be blank"
            )

        if self.guardrail_blocked and not self.guardrail_evaluated:
            raise ValueError(
                "guardrail_blocked requires guardrail_evaluated"
            )

        if (
            self.status is ReliabilityExecutionStatus.SUCCEEDED
            and self.failure_category is not None
        ):
            raise ValueError(
                "successful execution must not include "
                "failure_category"
            )

        if (
            self.status
            in {
                ReliabilityExecutionStatus.FAILED,
                ReliabilityExecutionStatus.TIMED_OUT,
            }
            and self.failure_category is None
        ):
            raise ValueError(
                "failed or timed-out execution requires "
                "failure_category"
            )

        if (
            self.recovery_status
            is ReliabilityRecoveryStatus.SUCCEEDED
            and self.status
            is not ReliabilityExecutionStatus.SUCCEEDED
        ):
            raise ValueError(
                "successful recovery requires successful "
                "execution status"
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
    def retried(self) -> bool:
        """Return whether execution required another attempt."""

        return self.attempt_count > 1

    @property
    def recovery_attempted(self) -> bool:
        """Return whether a recovery path was attempted."""

        return self.recovery_status is not (
            ReliabilityRecoveryStatus.NOT_ATTEMPTED
        )


class ReliabilityMetrics(BaseModel):
    """Aggregated execution reliability metrics."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    metrics_id: str
    total_executions: int = Field(ge=0)
    successful_executions: int = Field(ge=0)
    failed_executions: int = Field(ge=0)
    cancelled_executions: int = Field(ge=0)
    timed_out_executions: int = Field(ge=0)

    retried_executions: int = Field(ge=0)
    retry_successes: int = Field(ge=0)

    recovery_attempts: int = Field(ge=0)
    recovery_successes: int = Field(ge=0)
    manual_review_recoveries: int = Field(ge=0)

    guardrail_evaluations: int = Field(ge=0)
    guardrail_blocks: int = Field(ge=0)

    success_rate: float = Field(ge=0, le=1)
    failure_rate: float = Field(ge=0, le=1)
    cancellation_rate: float = Field(ge=0, le=1)
    timeout_rate: float = Field(ge=0, le=1)
    retry_rate: float = Field(ge=0, le=1)
    retry_success_rate: float = Field(ge=0, le=1)
    recovery_attempt_rate: float = Field(ge=0, le=1)
    recovery_success_rate: float = Field(ge=0, le=1)
    guardrail_block_rate: float = Field(ge=0, le=1)

    mean_duration_seconds: float = Field(ge=0)
    p50_duration_seconds: float = Field(ge=0)
    p95_duration_seconds: float = Field(ge=0)
    maximum_duration_seconds: float = Field(ge=0)

    failure_category_counts: dict[
        RetryFailureCategory,
        int,
    ] = Field(default_factory=dict)

    summary: str

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        """Validate aggregate count consistency."""

        if not self.metrics_id.strip():
            raise ValueError(
                "metrics_id must not be blank"
            )

        if not self.summary.strip():
            raise ValueError(
                "summary must not be blank"
            )

        terminal_total = (
            self.successful_executions
            + self.failed_executions
            + self.cancelled_executions
            + self.timed_out_executions
        )

        if terminal_total != self.total_executions:
            raise ValueError(
                "execution status counts must equal "
                "total_executions"
            )

        if self.retry_successes > self.retried_executions:
            raise ValueError(
                "retry_successes must not exceed "
                "retried_executions"
            )

        if self.recovery_successes > self.recovery_attempts:
            raise ValueError(
                "recovery_successes must not exceed "
                "recovery_attempts"
            )

        if self.manual_review_recoveries > self.recovery_attempts:
            raise ValueError(
                "manual_review_recoveries must not exceed "
                "recovery_attempts"
            )

        if self.guardrail_blocks > self.guardrail_evaluations:
            raise ValueError(
                "guardrail_blocks must not exceed "
                "guardrail_evaluations"
            )

        if any(
            count < 0
            for count in self.failure_category_counts.values()
        ):
            raise ValueError(
                "failure category counts must be nonnegative"
            )

        return self
