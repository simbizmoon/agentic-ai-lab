"""Schemas for deterministic tool execution."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ToolExecutionStatus(StrEnum):
    """Outcome states for one tool execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ToolExecutionRequest(BaseModel):
    """Input supplied to one registered tool."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    step_id: str
    description: str
    arguments: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_request(
        self,
    ) -> ToolExecutionRequest:
        """Validate execution request text."""

        if not self.step_id.strip():
            raise ValueError(
                "step_id must not be blank"
            )

        if not self.description.strip():
            raise ValueError(
                "description must not be blank"
            )

        return self


class ToolExecutionResult(BaseModel):
    """Normalized result returned by one tool."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    tool_name: str
    status: ToolExecutionStatus
    output: Any | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> ToolExecutionResult:
        """Validate success and failure result consistency."""

        if not self.tool_name.strip():
            raise ValueError(
                "tool_name must not be blank"
            )

        if (
            self.error_message is not None
            and not self.error_message.strip()
        ):
            raise ValueError(
                "error_message must not be blank"
            )

        if (
            self.status is ToolExecutionStatus.SUCCEEDED
            and self.error_message is not None
        ):
            raise ValueError(
                "successful execution must not have "
                "an error message"
            )

        if (
            self.status is ToolExecutionStatus.FAILED
            and self.error_message is None
        ):
            raise ValueError(
                "failed execution requires an error message"
            )

        return self
