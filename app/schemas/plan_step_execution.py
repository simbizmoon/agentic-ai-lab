"""Schemas for executing one structured plan step."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from app.schemas.tool_execution import (
    ToolExecutionResult,
)


class PlanStepExecutionStatus(StrEnum):
    """Outcome states for one plan-step execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TOOL_NOT_FOUND = "tool_not_found"
    STEP_NOT_EXECUTABLE = "step_not_executable"


class PlanStepExecutionResult(BaseModel):
    """Normalized outcome of executing one plan step."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
    )

    step_id: str
    tool_name: str | None = None
    status: PlanStepExecutionStatus
    tool_result: ToolExecutionResult | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_result(
        self,
    ) -> PlanStepExecutionResult:
        """Validate execution-result consistency."""

        if not self.step_id.strip():
            raise ValueError(
                "step_id must not be blank"
            )

        if (
            self.tool_name is not None
            and not self.tool_name.strip()
        ):
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
            self.status
            is PlanStepExecutionStatus.SUCCEEDED
        ):
            if self.tool_result is None:
                raise ValueError(
                    "successful step execution requires "
                    "a tool result"
                )

            if self.error_message is not None:
                raise ValueError(
                    "successful step execution must not "
                    "have an error message"
                )

        if (
            self.status
            is not PlanStepExecutionStatus.SUCCEEDED
            and self.error_message is None
        ):
            raise ValueError(
                "unsuccessful step execution requires "
                "an error message"
            )

        if (
            self.tool_result is not None
            and self.tool_name
            != self.tool_result.tool_name
        ):
            raise ValueError(
                "step tool name must match tool result"
            )

        return self
