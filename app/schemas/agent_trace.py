"""Schemas for recording structured planning-agent traces."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class AgentTraceEventType(StrEnum):
    """Stable event types emitted by planning agents."""

    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"

    PLANNING_STARTED = "planning_started"
    PLANNING_COMPLETED = "planning_completed"
    PLANNING_FAILED = "planning_failed"

    PLAN_STARTED = "plan_started"
    PLAN_COMPLETED = "plan_completed"
    PLAN_FAILED = "plan_failed"
    PLAN_CANCELLED = "plan_cancelled"
    PLAN_BLOCKED = "plan_blocked"

    STEP_STARTED = "step_started"
    STEP_COMPLETED = "step_completed"
    STEP_FAILED = "step_failed"
    STEP_SKIPPED = "step_skipped"

    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"

    EVALUATION_COMPLETED = "evaluation_completed"

    REPLANNING_STARTED = "replanning_started"
    REPLANNING_COMPLETED = "replanning_completed"
    REPLANNING_FAILED = "replanning_failed"

    REPLAN_LIMIT_REACHED = "replan_limit_reached"


class AgentTraceEvent(BaseModel):
    """One immutable structured agent trace event."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    trace_id: str
    sequence: int = Field(ge=1)
    event_type: AgentTraceEventType
    occurred_at: datetime

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
    def validate_event(self) -> AgentTraceEvent:
        """Validate trace identifiers and optional text."""

        required_text = {
            "trace_id": self.trace_id,
            "message": self.message,
        }

        for name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
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

        if self.occurred_at.tzinfo is None:
            raise ValueError(
                "occurred_at must be timezone-aware"
            )

        return self
