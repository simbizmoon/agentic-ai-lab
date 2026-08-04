"""Persistent background job schemas and lifecycle state."""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)


class ApplicationJobType(StrEnum):
    """Type of background work represented by a job."""

    RESEARCH_EXECUTION = "research_execution"
    AGENT_EXECUTION = "agent_execution"
    TOOL_EXECUTION = "tool_execution"
    WORKFLOW_EXECUTION = "workflow_execution"
    EVALUATION = "evaluation"
    RETRY_EXECUTION = "retry_execution"
    RELIABILITY_AGGREGATION = "reliability_aggregation"
    CLEANUP = "cleanup"
    CUSTOM = "custom"


class ApplicationJobStatus(StrEnum):
    """Persistent job lifecycle status."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"
    DEAD_LETTERED = "dead_lettered"


class ApplicationJobPriority(IntEnum):
    """Normalized job-processing priority."""

    LOW = 10
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


class ApplicationJobFailureCategory(StrEnum):
    """Normalized persistent job failure category."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    EXECUTION = "execution"
    VALIDATION = "validation"
    PERMISSION = "permission"
    POLICY = "policy"
    CONFLICT = "conflict"
    INTERNAL = "internal"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ApplicationJobFailure(BaseModel):
    """Persistent failure attached to a background job."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    category: ApplicationJobFailureCategory
    code: str
    message: str
    retryable: bool
    retry_reason: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate job failure information."""

        if not self.code.strip():
            raise ValueError("code must not be blank")

        if not self.message.strip():
            raise ValueError("message must not be blank")

        if self.retryable and (
            self.retry_reason is None
            or not self.retry_reason.strip()
        ):
            raise ValueError(
                "retryable failure requires retry_reason"
            )

        if (
            not self.retryable
            and self.retry_reason is not None
        ):
            raise ValueError(
                "nonretryable failure must not include "
                "retry_reason"
            )

        return self


class ApplicationJobCancellation(BaseModel):
    """Persistent cancellation request for one job."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    cancellation_id: str
    requested_at: datetime
    requested_by: str
    reason: str
    force: bool = False

    @model_validator(mode="after")
    def validate_cancellation(self) -> Self:
        """Validate cancellation request fields."""

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

        return self


class ApplicationJobLease(BaseModel):
    """Worker lease that temporarily owns one queued job."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    lease_id: str
    worker_id: str
    acquired_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_lease(self) -> Self:
        """Validate worker lease timing."""

        if not self.lease_id.strip():
            raise ValueError(
                "lease_id must not be blank"
            )

        if not self.worker_id.strip():
            raise ValueError(
                "worker_id must not be blank"
            )

        if self.acquired_at.tzinfo is None:
            raise ValueError(
                "acquired_at must be timezone-aware"
            )

        if self.expires_at.tzinfo is None:
            raise ValueError(
                "expires_at must be timezone-aware"
            )

        if self.expires_at <= self.acquired_at:
            raise ValueError(
                "expires_at must be later than acquired_at"
            )

        return self

    def active_at(self, now: datetime) -> bool:
        """Return whether the lease is active at a time."""

        if now.tzinfo is None:
            raise ValueError(
                "now must be timezone-aware"
            )

        return self.acquired_at <= now < self.expires_at


class ApplicationJobRecord(BaseModel):
    """Persistent application background-job record."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    job_id: str
    root_job_id: str
    parent_job_id: str | None = None
    previous_attempt_job_id: str | None = None

    request_id: str
    workspace_id: str
    execution_id: str | None = None

    job_type: ApplicationJobType
    queue_name: str
    priority: ApplicationJobPriority = (
        ApplicationJobPriority.NORMAL
    )

    status: ApplicationJobStatus

    payload: dict[str, JsonValue] = Field(default_factory=dict)

    attempt_number: int = Field(default=1, ge=1)
    maximum_attempts: int = Field(default=1, ge=1)

    available_at: datetime
    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    lease: ApplicationJobLease | None = None
    failure: ApplicationJobFailure | None = None
    cancellation: ApplicationJobCancellation | None = None

    record_version: int = Field(default=1, ge=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate persistent job invariants."""

        required_text = {
            "job_id": self.job_id,
            "root_job_id": self.root_job_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "queue_name": self.queue_name,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        optional_text = {
            "parent_job_id": self.parent_job_id,
            "previous_attempt_job_id": (
                self.previous_attempt_job_id
            ),
            "execution_id": self.execution_id,
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        if self.attempt_number > self.maximum_attempts:
            raise ValueError(
                "attempt_number must not exceed "
                "maximum_attempts"
            )

        if (
            self.attempt_number == 1
            and self.previous_attempt_job_id is not None
        ):
            raise ValueError(
                "first attempt must not include "
                "previous_attempt_job_id"
            )

        if (
            self.attempt_number > 1
            and (
                self.previous_attempt_job_id is None
                or not self.previous_attempt_job_id.strip()
            )
        ):
            raise ValueError(
                "retry attempt requires "
                "previous_attempt_job_id"
            )

        self._validate_timestamps()
        self._validate_status_contract()
        self._validate_metadata()

        return self

    def _validate_timestamps(self) -> None:
        """Validate timezone awareness and ordering."""

        timestamps = {
            "available_at": self.available_at,
            "created_at": self.created_at,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

        for field_name, value in timestamps.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        if self.available_at < self.created_at:
            raise ValueError(
                "available_at must not precede created_at"
            )

        ordered = [
            value
            for value in (
                self.queued_at,
                self.started_at,
                self.finished_at,
            )
            if value is not None
        ]

        previous = self.created_at

        for value in ordered:
            if value < previous:
                raise ValueError(
                    "job timestamps must be "
                    "chronologically ordered"
                )

            previous = value

    def _validate_status_contract(self) -> None:
        """Validate lifecycle-specific job fields."""

        terminal_statuses = {
            ApplicationJobStatus.SUCCEEDED,
            ApplicationJobStatus.FAILED,
            ApplicationJobStatus.CANCELLED,
            ApplicationJobStatus.DEAD_LETTERED,
        }

        leased_statuses = {
            ApplicationJobStatus.LEASED,
            ApplicationJobStatus.RUNNING,
        }

        failure_statuses = {
            ApplicationJobStatus.FAILED,
            ApplicationJobStatus.RETRY_SCHEDULED,
            ApplicationJobStatus.DEAD_LETTERED,
        }

        cancellation_statuses = {
            ApplicationJobStatus.CANCELLATION_REQUESTED,
            ApplicationJobStatus.CANCELLED,
        }

        if (
            self.status in terminal_statuses
            and self.finished_at is None
        ):
            raise ValueError(
                "terminal job requires finished_at"
            )

        if (
            self.status not in terminal_statuses
            and self.finished_at is not None
        ):
            raise ValueError(
                "nonterminal job must not include finished_at"
            )

        if (
            self.status is ApplicationJobStatus.RUNNING
            and self.started_at is None
        ):
            raise ValueError(
                "running job requires started_at"
            )

        if self.status in leased_statuses and self.lease is None:
            raise ValueError(
                "leased or running job requires lease"
            )

        if (
            self.status not in leased_statuses
            and self.lease is not None
        ):
            raise ValueError(
                "lease is only valid for leased or running job"
            )

        if (
            self.status in failure_statuses
            and self.failure is None
        ):
            raise ValueError(
                "failure status requires failure information"
            )

        if (
            self.status not in failure_statuses
            and self.failure is not None
        ):
            raise ValueError(
                "failure information is only valid for "
                "failure status"
            )

        if (
            self.status in cancellation_statuses
            and self.cancellation is None
        ):
            raise ValueError(
                "cancellation status requires "
                "cancellation information"
            )

        if (
            self.status not in cancellation_statuses
            and self.cancellation is not None
        ):
            raise ValueError(
                "cancellation information is only valid for "
                "cancellation status"
            )

        if (
            self.status is ApplicationJobStatus.RETRY_SCHEDULED
            and self.attempt_number >= self.maximum_attempts
        ):
            raise ValueError(
                "retry_scheduled job requires another "
                "available attempt"
            )

    def _validate_metadata(self) -> None:
        """Validate metadata text."""

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

    @property
    def terminal(self) -> bool:
        """Return whether the job is terminal."""

        return self.status in {
            ApplicationJobStatus.SUCCEEDED,
            ApplicationJobStatus.FAILED,
            ApplicationJobStatus.CANCELLED,
            ApplicationJobStatus.DEAD_LETTERED,
        }

    @property
    def retry_available(self) -> bool:
        """Return whether another attempt may be scheduled."""

        return (
            self.status
            in {
                ApplicationJobStatus.FAILED,
                ApplicationJobStatus.RETRY_SCHEDULED,
            }
            and self.failure is not None
            and self.failure.retryable
            and self.attempt_number < self.maximum_attempts
        )

    def available_for_queue_at(self, now: datetime) -> bool:
        """Return whether the job can enter the queue."""

        if now.tzinfo is None:
            raise ValueError(
                "now must be timezone-aware"
            )

        return (
            self.status
            in {
                ApplicationJobStatus.PENDING,
                ApplicationJobStatus.SCHEDULED,
                ApplicationJobStatus.RETRY_SCHEDULED,
            }
            and self.available_at <= now
        )
