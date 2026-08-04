"""Persistent application idempotency record schemas."""

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


class ApplicationIdempotencyStatus(StrEnum):
    """Lifecycle status of an idempotent operation."""

    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ApplicationIdempotencyFailure(BaseModel):
    """Persistent failure associated with an operation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    code: str
    message: str
    retryable: bool = False

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate failure text."""

        if not self.code.strip():
            raise ValueError("code must not be blank")

        if not self.message.strip():
            raise ValueError("message must not be blank")

        return self


class ApplicationIdempotencyRecord(BaseModel):
    """Persistent record for one idempotent operation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    idempotency_record_id: str
    workspace_id: str
    operation: str
    idempotency_key: str
    request_fingerprint: str

    status: ApplicationIdempotencyStatus
    result: JsonValue | None = None
    failure: ApplicationIdempotencyFailure | None = None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    record_version: int = Field(default=1, ge=1)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        """Validate idempotency invariants."""

        required_text = {
            "idempotency_record_id": self.idempotency_record_id,
            "workspace_id": self.workspace_id,
            "operation": self.operation,
            "idempotency_key": self.idempotency_key,
            "request_fingerprint": self.request_fingerprint,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if len(self.request_fingerprint) != 64:
            raise ValueError(
                "request_fingerprint must be a SHA-256 hex digest"
            )

        for field_name, value in {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }.items():
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware"
                )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at must not precede created_at"
            )

        if (
            self.completed_at is not None
            and self.completed_at < self.created_at
        ):
            raise ValueError(
                "completed_at must not precede created_at"
            )

        if (
            self.status is ApplicationIdempotencyStatus.IN_PROGRESS
            and (
                self.result is not None
                or self.failure is not None
                or self.completed_at is not None
            )
        ):
            raise ValueError(
                "in-progress record must not contain "
                "result, failure, or completed_at"
            )

        if self.status is ApplicationIdempotencyStatus.SUCCEEDED:
            if self.result is None:
                raise ValueError(
                    "succeeded record requires result"
                )

            if self.failure is not None:
                raise ValueError(
                    "succeeded record must not contain failure"
                )

            if self.completed_at is None:
                raise ValueError(
                    "succeeded record requires completed_at"
                )

        if self.status is ApplicationIdempotencyStatus.FAILED:
            if self.failure is None:
                raise ValueError(
                    "failed record requires failure"
                )

            if self.result is not None:
                raise ValueError(
                    "failed record must not contain result"
                )

            if self.completed_at is None:
                raise ValueError(
                    "failed record requires completed_at"
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
