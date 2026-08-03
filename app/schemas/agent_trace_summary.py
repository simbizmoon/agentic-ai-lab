"""Summary schemas for planning-agent traces."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class AgentTraceOutcome(StrEnum):
    """Final high-level trace outcome."""

    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class AgentTraceSummary(BaseModel):
    """Aggregated statistics for one planning-agent trace."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    outcome: AgentTraceOutcome

    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=0)

    event_count: int = Field(ge=1)
    attempt_count: int = Field(ge=0)
    plan_count: int = Field(ge=0)

    planning_count: int = Field(ge=0)
    replanning_count: int = Field(ge=0)

    step_started_count: int = Field(ge=0)
    step_completed_count: int = Field(ge=0)
    step_failed_count: int = Field(ge=0)
    step_skipped_count: int = Field(ge=0)

    tool_started_count: int = Field(ge=0)
    tool_completed_count: int = Field(ge=0)
    tool_failed_count: int = Field(ge=0)

    final_plan_id: str | None = None
    final_message: str

    @model_validator(mode="after")
    def validate_summary(
        self,
    ) -> AgentTraceSummary:
        """Validate summary values and consistency."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        if not self.final_message.strip():
            raise ValueError(
                "final_message must not be blank"
            )

        if (
            self.started_at.tzinfo is None
            or self.ended_at.tzinfo is None
        ):
            raise ValueError(
                "summary timestamps must be timezone-aware"
            )

        if self.ended_at < self.started_at:
            raise ValueError(
                "summary ended_at must not precede started_at"
            )

        if (
            self.final_plan_id is not None
            and not self.final_plan_id.strip()
        ):
            raise ValueError(
                "final_plan_id must not be blank"
            )

        calculated_duration = int(
            (
                self.ended_at - self.started_at
            ).total_seconds()
            * 1_000
        )

        if self.duration_ms != calculated_duration:
            raise ValueError(
                "summary duration_ms is inconsistent"
            )

        if (
            self.step_completed_count
            + self.step_failed_count
            + self.step_skipped_count
            > self.step_started_count
        ):
            raise ValueError(
                "finished step count must not exceed "
                "started step count"
            )

        if (
            self.tool_completed_count
            + self.tool_failed_count
            > self.tool_started_count
        ):
            raise ValueError(
                "finished tool count must not exceed "
                "started tool count"
            )

        return self
