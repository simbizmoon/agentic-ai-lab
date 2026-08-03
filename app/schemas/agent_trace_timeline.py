"""Readable timeline schemas for planning-agent traces."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.agent_trace import AgentTraceEventType


class AgentTraceTimelineItem(BaseModel):
    """One readable item in an agent trace timeline."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    sequence: int = Field(ge=1)
    event_type: AgentTraceEventType
    occurred_at: datetime
    elapsed_ms: int = Field(ge=0)
    message: str

    plan_id: str | None = None
    step_id: str | None = None
    tool_name: str | None = None
    attempt_number: int | None = Field(
        default=None,
        ge=1,
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_item(
        self,
    ) -> AgentTraceTimelineItem:
        """Validate timeline item text and timestamp."""

        if not self.message.strip():
            raise ValueError(
                "timeline message must not be blank"
            )

        if self.occurred_at.tzinfo is None:
            raise ValueError(
                "timeline occurred_at must be timezone-aware"
            )

        optional_text = {
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
        }

        for name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        return self


class AgentTraceTimeline(BaseModel):
    """Ordered readable timeline for one trace."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=0)
    items: list[AgentTraceTimelineItem] = Field(
        min_length=1
    )

    @model_validator(mode="after")
    def validate_timeline(
        self,
    ) -> AgentTraceTimeline:
        """Validate timeline ordering and duration."""

        if not self.trace_id.strip():
            raise ValueError(
                "trace_id must not be blank"
            )

        if (
            self.started_at.tzinfo is None
            or self.ended_at.tzinfo is None
        ):
            raise ValueError(
                "timeline timestamps must be timezone-aware"
            )

        if self.ended_at < self.started_at:
            raise ValueError(
                "timeline ended_at must not precede started_at"
            )

        sequences = [
            item.sequence
            for item in self.items
        ]

        if sequences != sorted(sequences):
            raise ValueError(
                "timeline items must be ordered by sequence"
            )

        if len(sequences) != len(set(sequences)):
            raise ValueError(
                "timeline sequences must be unique"
            )

        if self.items[0].occurred_at != self.started_at:
            raise ValueError(
                "timeline started_at must match first item"
            )

        if self.items[-1].occurred_at != self.ended_at:
            raise ValueError(
                "timeline ended_at must match final item"
            )

        calculated_duration = int(
            (
                self.ended_at - self.started_at
            ).total_seconds()
            * 1_000
        )

        if self.duration_ms != calculated_duration:
            raise ValueError(
                "timeline duration_ms is inconsistent"
            )

        return self
