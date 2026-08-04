"""Application contracts for tool execution."""

from __future__ import annotations

from typing import Protocol, Self, runtime_checkable

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.application.execution_record import (
    ApplicationExecutionRecord,
)


class ApplicationToolExecutionRequest(BaseModel):
    """Application-level request to execute one tool."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    workspace_id: str
    tool_id: str
    operation: str

    arguments: dict[str, JsonValue] = Field(
        default_factory=dict
    )

    root_execution_id: str | None = None
    parent_execution_id: str | None = None
    previous_attempt_execution_id: str | None = None

    attempt_number: int = Field(default=1, ge=1)
    maximum_attempts: int = Field(default=1, ge=1)

    actor_id: str | None = None
    assignment_id: str | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate tool execution request fields."""

        required_text = {
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "tool_id": self.tool_id,
            "operation": self.operation,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        optional_text = {
            "root_execution_id": self.root_execution_id,
            "parent_execution_id": self.parent_execution_id,
            "previous_attempt_execution_id": (
                self.previous_attempt_execution_id
            ),
            "actor_id": self.actor_id,
            "assignment_id": self.assignment_id,
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        if self.attempt_number > self.maximum_attempts:
            raise ValueError(
                "attempt_number must not exceed "
                "maximum_attempts"
            )

        if (
            self.attempt_number == 1
            and self.previous_attempt_execution_id is not None
        ):
            raise ValueError(
                "first attempt must not include "
                "previous_attempt_execution_id"
            )

        if (
            self.attempt_number > 1
            and self.previous_attempt_execution_id is None
        ):
            raise ValueError(
                "retry attempt requires "
                "previous_attempt_execution_id"
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


class ApplicationToolExecutionOutput(BaseModel):
    """Normalized output returned by one tool."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    result: JsonValue
    summary: str
    artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        """Validate normalized tool output."""

        if not self.summary.strip():
            raise ValueError(
                "summary must not be blank"
            )

        if any(
            not artifact_id.strip()
            for artifact_id in self.artifact_ids
        ):
            raise ValueError(
                "artifact_ids must not contain blank values"
            )

        normalized = [
            artifact_id.strip().casefold()
            for artifact_id in self.artifact_ids
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "artifact_ids must not contain duplicates"
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


class ApplicationToolExecutionResult(BaseModel):
    """Successful application tool execution result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution: ApplicationExecutionRecord
    output: ApplicationToolExecutionOutput

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate successful tool execution result."""

        if not self.execution.terminal:
            raise ValueError(
                "tool execution result requires "
                "terminal execution"
            )

        return self


@runtime_checkable
class ToolExecutionRunner(Protocol):
    """Contract implemented by a concrete tool executor."""

    def execute(
        self,
        request: ApplicationToolExecutionRequest,
    ) -> ApplicationToolExecutionOutput:
        """Execute one tool request."""


@runtime_checkable
class ToolPermissionChecker(Protocol):
    """Contract used to authorize one tool execution."""

    def require_allowed(
        self,
        request: ApplicationToolExecutionRequest,
    ) -> None:
        """Raise PermissionError when execution is forbidden."""
