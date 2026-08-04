"""Schemas for application retry scheduling results."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.application.job_record import (
    ApplicationJobRecord,
)
from app.guardrails.retry_decision import (
    RetryDecision,
    RetryDecisionType,
)


class ApplicationRetrySchedulingStatus(StrEnum):
    """Outcome of one retry scheduling request."""

    SCHEDULED = "scheduled"
    STOPPED = "stopped"


class ApplicationRetrySchedulingResult(BaseModel):
    """Complete result of retry scheduling."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    scheduling_id: str
    source_job_id: str
    status: ApplicationRetrySchedulingStatus
    retry_decision: RetryDecision
    scheduled_job: ApplicationJobRecord | None = None
    summary: str
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate scheduling-result consistency."""

        required_text = {
            "scheduling_id": self.scheduling_id,
            "source_job_id": self.source_job_id,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.status
            is ApplicationRetrySchedulingStatus.SCHEDULED
        ):
            if (
                self.retry_decision.decision
                is not RetryDecisionType.RETRY
            ):
                raise ValueError(
                    "scheduled result requires retry decision"
                )

            if self.scheduled_job is None:
                raise ValueError(
                    "scheduled result requires scheduled_job"
                )

            if (
                self.scheduled_job.previous_attempt_job_id
                != self.source_job_id
            ):
                raise ValueError(
                    "scheduled job must reference source job"
                )

        if (
            self.status
            is ApplicationRetrySchedulingStatus.STOPPED
        ):
            if (
                self.retry_decision.decision
                is not RetryDecisionType.STOP
            ):
                raise ValueError(
                    "stopped result requires stop decision"
                )

            if self.scheduled_job is not None:
                raise ValueError(
                    "stopped result must not include "
                    "scheduled_job"
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
