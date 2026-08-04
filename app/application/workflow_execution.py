"""Application contracts for workflow execution."""

from __future__ import annotations

from enum import StrEnum
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


class ApplicationWorkflowStepStatus(StrEnum):
    """Normalized outcome of one workflow step."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class ApplicationWorkflowExecutionRequest(BaseModel):
    """Application-level request to execute one workflow."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    workspace_id: str
    workflow_id: str
    objective: str

    input_payload: dict[str, JsonValue] = Field(
        default_factory=dict
    )

    root_execution_id: str | None = None
    parent_execution_id: str | None = None
    previous_attempt_execution_id: str | None = None

    attempt_number: int = Field(default=1, ge=1)
    maximum_attempts: int = Field(default=1, ge=1)

    actor_id: str | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate workflow execution request fields."""

        required_text = {
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "workflow_id": self.workflow_id,
            "objective": self.objective,
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


class ApplicationWorkflowStepResult(BaseModel):
    """Normalized result of one workflow step."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    step_id: str
    step_type: str
    status: ApplicationWorkflowStepStatus
    summary: str

    execution_id: str | None = None
    output: dict[str, JsonValue] = Field(
        default_factory=dict
    )
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_step(self) -> Self:
        """Validate one workflow step result."""

        required_text = {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        optional_text = {
            "execution_id": self.execution_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }

        for field_name, value in optional_text.items():
            if value is not None and not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank "
                    "when provided"
                )

        if (
            self.status
            is ApplicationWorkflowStepStatus.FAILED
            and (
                self.error_code is None
                or self.error_message is None
            )
        ):
            raise ValueError(
                "failed workflow step requires error details"
            )

        if (
            self.status
            is not ApplicationWorkflowStepStatus.FAILED
            and (
                self.error_code is not None
                or self.error_message is not None
            )
        ):
            raise ValueError(
                "nonfailed workflow step must not include "
                "error details"
            )

        return self


class ApplicationWorkflowExecutionOutput(BaseModel):
    """Normalized output returned by a workflow runner."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    summary: str
    result: dict[str, JsonValue] = Field(
        default_factory=dict
    )
    steps: list[ApplicationWorkflowStepResult] = Field(
        default_factory=list
    )
    artifact_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        """Validate normalized workflow output."""

        if not self.summary.strip():
            raise ValueError(
                "summary must not be blank"
            )

        step_ids = [
            step.step_id.strip().casefold()
            for step in self.steps
        ]

        if len(set(step_ids)) != len(step_ids):
            raise ValueError(
                "steps must have unique step IDs"
            )

        if any(
            step.status
            is ApplicationWorkflowStepStatus.FAILED
            for step in self.steps
        ):
            raise ValueError(
                "successful workflow output must not contain "
                "failed steps"
            )

        if any(
            not artifact_id.strip()
            for artifact_id in self.artifact_ids
        ):
            raise ValueError(
                "artifact_ids must not contain blank values"
            )

        normalized_artifacts = [
            artifact_id.strip().casefold()
            for artifact_id in self.artifact_ids
        ]

        if len(set(normalized_artifacts)) != len(
            normalized_artifacts
        ):
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


class ApplicationWorkflowExecutionResult(BaseModel):
    """Successful application workflow execution result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution: ApplicationExecutionRecord
    output: ApplicationWorkflowExecutionOutput

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate successful workflow result."""

        if not self.execution.terminal:
            raise ValueError(
                "workflow execution result requires "
                "terminal execution"
            )

        return self


@runtime_checkable
class WorkflowExecutionRunner(Protocol):
    """Contract implemented by a workflow engine."""

    def execute(
        self,
        request: ApplicationWorkflowExecutionRequest,
    ) -> ApplicationWorkflowExecutionOutput:
        """Execute one workflow request."""
