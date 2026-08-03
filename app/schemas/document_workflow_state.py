"""State model for the document Tool workflow."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.tool_workflow_event import ToolWorkflowEvent


class DocumentWorkflowStatus(StrEnum):
    """Stable lifecycle states for a document workflow."""

    RECEIVED = "received"
    MODEL_DECISION = "model_decision"
    TOOL_EXECUTION = "tool_execution"
    TOOL_CORRECTION = "tool_correction"
    FINAL_RESPONSE = "final_response"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentWorkflowState(BaseModel):
    """Mutable state carried through one document workflow."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: DocumentWorkflowStatus
    user_request: str = Field(min_length=1)

    selected_tool_name: str | None = None
    tool_call_id: str | None = None
    tool_arguments_json: str | None = None
    observation: dict[str, Any] | None = None
    final_answer: str | None = None

    correction_attempted: bool = False
    events: list[ToolWorkflowEvent] = Field(default_factory=list)

    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_state_consistency(self) -> DocumentWorkflowState:
        """Reject contradictory workflow state combinations."""

        if self.status == DocumentWorkflowStatus.COMPLETED:
            if not self.final_answer:
                raise ValueError(
                    "completed workflow requires final_answer"
                )

            if self.error_code is not None:
                raise ValueError(
                    "completed workflow must not contain error_code"
                )

            if self.error_message is not None:
                raise ValueError(
                    "completed workflow must not contain error_message"
                )

        if self.status == DocumentWorkflowStatus.FAILED:
            if not self.error_code:
                raise ValueError(
                    "failed workflow requires error_code"
                )

            if not self.error_message:
                raise ValueError(
                    "failed workflow requires error_message"
                )

        if (
            self.observation is not None
            and not self.selected_tool_name
        ):
            raise ValueError(
                "observation requires selected_tool_name"
            )

        if (
            self.tool_call_id is not None
            and not self.selected_tool_name
        ):
            raise ValueError(
                "tool_call_id requires selected_tool_name"
            )

        if (
            self.tool_arguments_json is not None
            and not self.selected_tool_name
        ):
            raise ValueError(
                "tool arguments require selected_tool_name"
            )

        return self
