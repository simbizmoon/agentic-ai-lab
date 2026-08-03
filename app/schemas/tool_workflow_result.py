"""Structured result for a single Tool Calling workflow."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.document_workflow_state import (
    DocumentWorkflowStatus,
)
from app.schemas.tool_workflow_event import ToolWorkflowEvent


class ToolWorkflowResult(BaseModel):
    """Preserve Tool usage, Observation, and final model answer."""

    model_config = ConfigDict(extra="forbid", strict=True)

    tool_used: bool
    tool_name: str | None = None
    observation: dict[str, Any] | None = None
    final_answer: str = Field(min_length=1)
    workflow_status: DocumentWorkflowStatus = (
        DocumentWorkflowStatus.COMPLETED
    )
    correction_attempted: bool = False
    events: list[ToolWorkflowEvent] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_tool_state(self) -> ToolWorkflowResult:
        """Ensure Tool metadata is internally consistent."""

        if self.tool_used:
            if not self.tool_name:
                raise ValueError(
                    "tool_name is required when tool_used is true"
                )

            if self.observation is None:
                raise ValueError(
                    "observation is required when tool_used is true"
                )
        else:
            if self.tool_name is not None:
                raise ValueError(
                    "tool_name must be absent when tool_used is false"
                )

            if self.observation is not None:
                raise ValueError(
                    "observation must be absent when tool_used is false"
                )

        if (
            self.workflow_status
            != DocumentWorkflowStatus.COMPLETED
        ):
            raise ValueError(
                "successful ToolWorkflowResult must be completed"
            )

        return self
