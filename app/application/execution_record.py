"""Persistent application execution record schemas."""

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


class ApplicationExecutionSubjectType(StrEnum):
    """Type of subject represented by an execution record."""

    AGENT = "agent"
    TOOL = "tool"
    ASSIGNMENT = "assignment"
    WORKFLOW = "workflow"
    EVALUATION = "evaluation"
    BACKGROUND_JOB = "background_job"


class ApplicationExecutionStatus(StrEnum):
    """Persistent lifecycle status of an execution."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ApplicationExecutionFailureCategory(StrEnum):
    """Persistent normalized execution failure category."""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"
    TOOL = "tool"
    VALIDATION = "validation"
    PERMISSION = "permission"
    POLICY = "policy"
    AUTHENTICATION = "authentication"
    CONFLICT = "conflict"
    INTERNAL = "internal"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ApplicationExecutionReference(BaseModel):
    """Reference to an execution input or output artifact."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    name: str
    reference_type: str
    reference_id: str
    primary: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        """Validate execution reference text."""

        required_text = {
            "name": self.name,
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_metadata(self.metadata)

        return self

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate metadata text."""

        for key, value in metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )


class ApplicationExecutionFailure(BaseModel):
    """Persistent failure information for one execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    category: ApplicationExecutionFailureCategory
    code: str
    message: str
    retryable: bool
    retry_reason: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate persistent failure information."""

        if not self.code.strip():
            raise ValueError(
                "code must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "message must not be blank"
            )

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


class ApplicationCancellationRecord(BaseModel):
    """Persistent cancellation request attached to execution."""

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
        """Validate cancellation request."""

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


class ApplicationExecutionRecord(BaseModel):
    """Persistent application-level execution state."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution_id: str
    root_execution_id: str
    parent_execution_id: str | None = None

    request_id: str
    workspace_id: str

    subject_type: ApplicationExecutionSubjectType
    subject_id: str

    status: ApplicationExecutionStatus

    attempt_number: int = Field(default=1, ge=1)
    maximum_attempts: int = Field(default=1, ge=1)
    previous_attempt_execution_id: str | None = None

    inputs: list[ApplicationExecutionReference] = Field(
        default_factory=list
    )
    outputs: list[ApplicationExecutionReference] = Field(
        default_factory=list
    )

    guardrail_evaluation_ids: list[str] = Field(
        default_factory=list
    )
    retry_decision_ids: list[str] = Field(
        default_factory=list
    )
    recovery_decision_id: str | None = None

    failure: ApplicationExecutionFailure | None = None
    cancellation: ApplicationCancellationRecord | None = None

    created_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    deadline_at: datetime | None = None

    record_version: int = Field(default=1, ge=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate persistent execution invariants."""

        required_text = {
            "execution_id": self.execution_id,
            "root_execution_id": self.root_execution_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "subject_id": self.subject_id,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.parent_execution_id is not None
            and not self.parent_execution_id.strip()
        ):
            raise ValueError(
                "parent_execution_id must not be blank "
                "when provided"
            )

        if self.attempt_number > self.maximum_attempts:
            raise ValueError(
                "attempt_number must not exceed "
                "maximum_attempts"
            )

        if (
            self.attempt_number == 1
            and self.previous_attempt_execution_id is not None
        ):
            raise ValueError(
                "first attempt must not include "
                "previous_attempt_execution_id"
            )

        if (
            self.attempt_number > 1
            and (
                self.previous_attempt_execution_id is None
                or not self.previous_attempt_execution_id.strip()
            )
        ):
            raise ValueError(
                "retry attempt requires "
                "previous_attempt_execution_id"
            )

        self._validate_reference_uniqueness(
            self.inputs,
            field_name="inputs",
        )
        self._validate_reference_uniqueness(
            self.outputs,
            field_name="outputs",
        )

        self._validate_unique_text(
            self.guardrail_evaluation_ids,
            field_name="guardrail_evaluation_ids",
        )
        self._validate_unique_text(
            self.retry_decision_ids,
            field_name="retry_decision_ids",
        )

        if (
            self.recovery_decision_id is not None
            and not self.recovery_decision_id.strip()
        ):
            raise ValueError(
                "recovery_decision_id must not be blank "
                "when provided"
            )

        self._validate_timestamps()
        self._validate_status_contract()
        self._validate_metadata(self.metadata)

        return self

    def _validate_timestamps(self) -> None:
        """Validate timezone and timestamp ordering."""

        timestamps = {
            "created_at": self.created_at,
            "queued_at": self.queued_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "deadline_at": self.deadline_at,
        }

        for field_name, value in timestamps.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        ordered_values = [
            value
            for value in (
                self.queued_at,
                self.started_at,
                self.finished_at,
            )
            if value is not None
        ]

        previous = self.created_at

        for value in ordered_values:
            if value < previous:
                raise ValueError(
                    "execution timestamps must be "
                    "chronologically ordered"
                )

            previous = value

    def _validate_status_contract(self) -> None:
        """Validate fields required by lifecycle status."""

        terminal_statuses = {
            ApplicationExecutionStatus.SUCCEEDED,
            ApplicationExecutionStatus.FAILED,
            ApplicationExecutionStatus.CANCELLED,
            ApplicationExecutionStatus.TIMED_OUT,
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

        if (
            self.status is ApplicationExecutionStatus.RUNNING
            and self.started_at is None
        ):
            raise ValueError(
                "running execution requires started_at"
            )

        if (
            self.status
            in {
                ApplicationExecutionStatus.SUCCEEDED,
                ApplicationExecutionStatus.FAILED,
                ApplicationExecutionStatus.CANCELLED,
                ApplicationExecutionStatus.TIMED_OUT,
            }
            and self.started_at is None
        ):
            raise ValueError(
                "terminal execution requires started_at"
            )

        if (
            self.status is ApplicationExecutionStatus.SUCCEEDED
            and self.failure is not None
        ):
            raise ValueError(
                "successful execution must not include failure"
            )

        failure_statuses = {
            ApplicationExecutionStatus.FAILED,
            ApplicationExecutionStatus.TIMED_OUT,
        }

        if (
            self.status in failure_statuses
            and self.failure is None
        ):
            raise ValueError(
                "failed or timed-out execution requires failure"
            )

        if (
            self.status not in failure_statuses
            and self.failure is not None
        ):
            raise ValueError(
                "failure is only valid for failed or "
                "timed-out execution"
            )

        cancellation_statuses = {
            ApplicationExecutionStatus.CANCELLATION_REQUESTED,
            ApplicationExecutionStatus.CANCELLED,
        }

        if (
            self.status in cancellation_statuses
            and self.cancellation is None
        ):
            raise ValueError(
                "cancellation status requires "
                "cancellation record"
            )

        if (
            self.status not in cancellation_statuses
            and self.cancellation is not None
        ):
            raise ValueError(
                "cancellation record is only valid for "
                "cancellation status"
            )

    @staticmethod
    def _validate_reference_uniqueness(
        references: list[ApplicationExecutionReference],
        *,
        field_name: str,
    ) -> None:
        """Validate reference IDs within one collection."""

        reference_ids = [
            reference.reference_id.strip().casefold()
            for reference in references
        ]

        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError(
                f"{field_name} must have unique reference IDs"
            )

        primary_count = sum(
            reference.primary
            for reference in references
        )

        if primary_count > 1:
            raise ValueError(
                f"{field_name} must not contain multiple "
                "primary references"
            )

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique nonblank text values."""

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

    @staticmethod
    def _validate_metadata(
        metadata: dict[str, str],
    ) -> None:
        """Validate record metadata."""

        for key, value in metadata.items():
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
        """Return whether execution is terminal."""

        return self.status in {
            ApplicationExecutionStatus.SUCCEEDED,
            ApplicationExecutionStatus.FAILED,
            ApplicationExecutionStatus.CANCELLED,
            ApplicationExecutionStatus.TIMED_OUT,
        }

    @property
    def retry_available(self) -> bool:
        """Return whether another attempt is available."""

        return (
            self.status
            in {
                ApplicationExecutionStatus.FAILED,
                ApplicationExecutionStatus.TIMED_OUT,
            }
            and self.failure is not None
            and self.failure.retryable
            and self.attempt_number < self.maximum_attempts
        )
