"""Schemas for deterministic retry decisions."""

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

from app.guardrails.retry_policy import RetryFailureCategory


class RetryDecisionType(StrEnum):
    """Final retry decision."""

    RETRY = "retry"
    STOP = "stop"


class RetryStopReason(StrEnum):
    """Reason a retry request was stopped."""

    NONE = "none"
    FAILURE_NOT_RETRYABLE = "failure_not_retryable"
    CATEGORY_DENIED = "category_denied"
    CATEGORY_NOT_ALLOWED = "category_not_allowed"
    ERROR_CODE_DENIED = "error_code_denied"
    ERROR_CODE_NOT_ALLOWED = "error_code_not_allowed"
    MAXIMUM_ATTEMPTS_REACHED = "maximum_attempts_reached"


class RetryFailureContext(BaseModel):
    """Normalized failure supplied to retry evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    failure_id: str
    category: RetryFailureCategory
    error_code: str
    message: str
    retryable: bool
    attempt_number: int = Field(ge=1)
    retry_after_seconds: float | None = Field(
        default=None,
        ge=0,
    )
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate failure identity and retry metadata."""

        required_text = {
            "failure_id": self.failure_id,
            "error_code": self.error_code,
            "message": self.message,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class RetryDecision(BaseModel):
    """Complete retry decision and computed delay."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    decision_id: str
    policy_id: str
    failure_id: str
    decision: RetryDecisionType
    stop_reason: RetryStopReason = RetryStopReason.NONE
    current_attempt: int = Field(ge=1)
    next_attempt: int | None = Field(default=None, ge=2)
    delay_seconds: float | None = Field(default=None, ge=0)
    used_retry_after: bool = False
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        """Validate retry and stop decision consistency."""

        required_text = {
            "decision_id": self.decision_id,
            "policy_id": self.policy_id,
            "failure_id": self.failure_id,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if self.decision is RetryDecisionType.RETRY:
            if self.stop_reason is not RetryStopReason.NONE:
                raise ValueError(
                    "retry decision must not include stop_reason"
                )

            if self.next_attempt is None:
                raise ValueError(
                    "retry decision must include next_attempt"
                )

            if self.next_attempt != self.current_attempt + 1:
                raise ValueError(
                    "next_attempt must equal current_attempt + 1"
                )

            if self.delay_seconds is None:
                raise ValueError(
                    "retry decision must include delay_seconds"
                )

        if self.decision is RetryDecisionType.STOP:
            if self.stop_reason is RetryStopReason.NONE:
                raise ValueError(
                    "stop decision must include stop_reason"
                )

            if self.next_attempt is not None:
                raise ValueError(
                    "stop decision must not include next_attempt"
                )

            if self.delay_seconds is not None:
                raise ValueError(
                    "stop decision must not include delay_seconds"
                )

            if self.used_retry_after:
                raise ValueError(
                    "stop decision must not use retry_after"
                )

        return self
