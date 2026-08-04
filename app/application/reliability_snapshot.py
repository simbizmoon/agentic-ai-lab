"""Application-level reliability query result schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ApplicationExecutionReliabilityMetrics(BaseModel):
    """Aggregated reliability metrics for execution records."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    total: int = Field(ge=0)
    pending: int = Field(ge=0)
    queued: int = Field(ge=0)
    running: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    cancellation_requested: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    timed_out: int = Field(ge=0)
    retry_attempts: int = Field(ge=0)

    success_rate: float = Field(ge=0, le=1)
    failure_rate: float = Field(ge=0, le=1)
    cancellation_rate: float = Field(ge=0, le=1)
    timeout_rate: float = Field(ge=0, le=1)
    retry_rate: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        """Validate execution count consistency."""

        status_total = (
            self.pending
            + self.queued
            + self.running
            + self.succeeded
            + self.failed
            + self.cancellation_requested
            + self.cancelled
            + self.timed_out
        )

        if status_total != self.total:
            raise ValueError(
                "execution status counts must equal total"
            )

        if self.retry_attempts > self.total:
            raise ValueError(
                "execution retry_attempts must not exceed total"
            )

        return self


class ApplicationEvaluationReliabilityMetrics(BaseModel):
    """Aggregated reliability metrics for evaluations."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    error: int = Field(ge=0)
    skipped: int = Field(ge=0)
    blocking_results: int = Field(ge=0)

    pass_rate: float = Field(ge=0, le=1)
    error_rate: float = Field(ge=0, le=1)
    blocking_rate: float = Field(ge=0, le=1)
    average_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        """Validate evaluation count consistency."""

        status_total = (
            self.passed
            + self.failed
            + self.error
            + self.skipped
        )

        if status_total != self.total:
            raise ValueError(
                "evaluation status counts must equal total"
            )

        if self.blocking_results > self.total:
            raise ValueError(
                "blocking_results must not exceed total"
            )

        return self


class ApplicationGuardrailReliabilityMetrics(BaseModel):
    """Aggregated reliability metrics for guardrails."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    total: int = Field(ge=0)
    allowed: int = Field(ge=0)
    warned: int = Field(ge=0)
    blocked: int = Field(ge=0)

    total_violations: int = Field(ge=0)
    blocking_violations: int = Field(ge=0)
    warning_violations: int = Field(ge=0)

    allow_rate: float = Field(ge=0, le=1)
    warning_rate: float = Field(ge=0, le=1)
    blocking_rate: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        """Validate guardrail count consistency."""

        if (
            self.allowed + self.warned + self.blocked
            != self.total
        ):
            raise ValueError(
                "guardrail decision counts must equal total"
            )

        if (
            self.blocking_violations
            + self.warning_violations
            != self.total_violations
        ):
            raise ValueError(
                "guardrail violation counts must equal total"
            )

        return self


class ApplicationJobReliabilityMetrics(BaseModel):
    """Aggregated reliability metrics for background jobs."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    total: int = Field(ge=0)
    pending: int = Field(ge=0)
    scheduled: int = Field(ge=0)
    queued: int = Field(ge=0)
    leased: int = Field(ge=0)
    running: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    retry_scheduled: int = Field(ge=0)
    cancellation_requested: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    dead_lettered: int = Field(ge=0)
    retry_attempts: int = Field(ge=0)

    completion_rate: float = Field(ge=0, le=1)
    success_rate: float = Field(ge=0, le=1)
    failure_rate: float = Field(ge=0, le=1)
    dead_letter_rate: float = Field(ge=0, le=1)
    retry_rate: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_metrics(self) -> Self:
        """Validate job count consistency."""

        status_total = (
            self.pending
            + self.scheduled
            + self.queued
            + self.leased
            + self.running
            + self.succeeded
            + self.failed
            + self.retry_scheduled
            + self.cancellation_requested
            + self.cancelled
            + self.dead_lettered
        )

        if status_total != self.total:
            raise ValueError(
                "job status counts must equal total"
            )

        if self.retry_attempts > self.total:
            raise ValueError(
                "job retry_attempts must not exceed total"
            )

        return self


class ApplicationReliabilitySnapshot(BaseModel):
    """Complete application reliability snapshot."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    snapshot_id: str
    generated_at: datetime

    request_id: str | None = None
    workspace_id: str | None = None

    executions: ApplicationExecutionReliabilityMetrics
    evaluations: ApplicationEvaluationReliabilityMetrics
    guardrails: ApplicationGuardrailReliabilityMetrics
    jobs: ApplicationJobReliabilityMetrics

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        """Validate snapshot identity and timestamp."""

        if not self.snapshot_id.strip():
            raise ValueError(
                "snapshot_id must not be blank"
            )

        if self.generated_at.tzinfo is None:
            raise ValueError(
                "generated_at must be timezone-aware"
            )

        for field_name, value in {
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
        }.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        return self
