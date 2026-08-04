"""Persistent background-job cancellation request schemas."""

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


class ApplicationCancellationStatus(StrEnum):
    """Lifecycle status of a persisted cancellation request."""

    REQUESTED = "requested"
    ACKNOWLEDGED = "acknowledged"
    COMPLETED = "completed"


class ApplicationJobCancellationRequestRecord(BaseModel):
    """Persistent cancellation request associated with one job."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    cancellation_request_id: str
    job_id: str
    request_id: str
    workspace_id: str

    requested_by: str
    reason: str
    force: bool = False

    status: ApplicationCancellationStatus

    requested_at: datetime
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    completed_at: datetime | None = None
    completed_by: str | None = None

    record_version: int = Field(default=1, ge=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate cancellation-request invariants."""

        required_text = {
            "cancellation_request_id": (
                self.cancellation_request_id
            ),
            "job_id": self.job_id,
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "requested_by": self.requested_by,
            "reason": self.reason,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        optional_text = {
            "acknowledged_by": self.acknowledged_by,
            "completed_by": self.completed_by,
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        timestamps = {
            "requested_at": self.requested_at,
            "acknowledged_at": self.acknowledged_at,
            "completed_at": self.completed_at,
        }

        for field_name, value in timestamps.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        if (
            self.acknowledged_at is not None
            and self.acknowledged_at < self.requested_at
        ):
            raise ValueError(
                "acknowledged_at must not precede "
                "requested_at"
            )

        comparison_time = (
            self.acknowledged_at or self.requested_at
        )

        if (
            self.completed_at is not None
            and self.completed_at < comparison_time
        ):
            raise ValueError(
                "completed_at must not precede prior "
                "cancellation timestamps"
            )

        if (
            self.status
            is ApplicationCancellationStatus.REQUESTED
            and (
                self.acknowledged_at is not None
                or self.acknowledged_by is not None
                or self.completed_at is not None
                or self.completed_by is not None
            )
        ):
            raise ValueError(
                "requested cancellation must not include "
                "acknowledgement or completion"
            )

        if (
            self.status
            is ApplicationCancellationStatus.ACKNOWLEDGED
            and (
                self.acknowledged_at is None
                or self.acknowledged_by is None
            )
        ):
            raise ValueError(
                "acknowledged cancellation requires "
                "acknowledgement details"
            )

        if (
            self.status
            is ApplicationCancellationStatus.ACKNOWLEDGED
            and (
                self.completed_at is not None
                or self.completed_by is not None
            )
        ):
            raise ValueError(
                "acknowledged cancellation must not include "
                "completion details"
            )

        if (
            self.status
            is ApplicationCancellationStatus.COMPLETED
            and (
                self.completed_at is None
                or self.completed_by is None
            )
        ):
            raise ValueError(
                "completed cancellation requires "
                "completion details"
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
    def terminal(self) -> bool:
        """Return whether cancellation processing is complete."""

        return (
            self.status
            is ApplicationCancellationStatus.COMPLETED
        )
