"""Structured events produced by a Tool workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolWorkflowEventType(StrEnum):
    """Stable event types emitted by a Tool workflow."""

    REQUEST_RECEIVED = "request_received"
    DIRECT_RESPONSE = "direct_response"
    TOOL_SELECTED = "tool_selected"
    TOOL_EXECUTION_SUCCEEDED = "tool_execution_succeeded"
    TOOL_ARGUMENT_CORRECTION_REQUESTED = (
        "tool_argument_correction_requested"
    )
    TOOL_ARGUMENTS_CORRECTED = "tool_arguments_corrected"
    FINAL_RESPONSE_CREATED = "final_response_created"


class ToolWorkflowEvent(BaseModel):
    """One structured event in a Tool workflow."""

    model_config = ConfigDict(extra="forbid", strict=True)

    event_type: ToolWorkflowEventType
    tool_name: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_tool_name(self) -> ToolWorkflowEvent:
        """Require a Tool name for Tool-specific events."""

        tool_events = {
            ToolWorkflowEventType.TOOL_SELECTED,
            ToolWorkflowEventType.TOOL_EXECUTION_SUCCEEDED,
            ToolWorkflowEventType.TOOL_ARGUMENT_CORRECTION_REQUESTED,
            ToolWorkflowEventType.TOOL_ARGUMENTS_CORRECTED,
        }

        if self.event_type in tool_events and not self.tool_name:
            raise ValueError(
                "tool_name is required for Tool-specific events"
            )

        if self.event_type not in tool_events and self.tool_name is not None:
            raise ValueError(
                "tool_name is not allowed for non-Tool events"
            )

        return self
