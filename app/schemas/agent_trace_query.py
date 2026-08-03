"""Query schemas for planning-agent traces."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.agent_trace import AgentTraceEventType


class AgentTraceQuery(BaseModel):
    """Filters for retrieving recorded trace events."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    trace_id: str | None = None
    event_types: list[AgentTraceEventType] = Field(
        default_factory=list
    )
    plan_id: str | None = None
    step_id: str | None = None
    tool_name: str | None = None
    attempt_number: int | None = Field(
        default=None,
        ge=1,
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=10_000,
    )

    @model_validator(mode="after")
    def validate_query(
        self,
    ) -> AgentTraceQuery:
        """Reject blank optional query identifiers."""

        optional_text = {
            "trace_id": self.trace_id,
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "tool_name": self.tool_name,
        }

        for name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{name} must not be blank"
                )

        if len(self.event_types) != len(
            set(self.event_types)
        ):
            raise ValueError(
                "event types must be unique"
            )

        return self
