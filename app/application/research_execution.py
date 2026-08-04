"""Application contracts for research execution."""

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


class ApplicationResearchExecutionRequest(BaseModel):
    """Application-level request to execute a research agent."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    workspace_id: str
    agent_id: str
    query: str

    root_execution_id: str | None = None
    parent_execution_id: str | None = None
    previous_attempt_execution_id: str | None = None

    attempt_number: int = Field(default=1, ge=1)
    maximum_attempts: int = Field(default=1, ge=1)

    context: dict[str, JsonValue] = Field(
        default_factory=dict
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Validate research execution request fields."""

        required_text = {
            "request_id": self.request_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "query": self.query,
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


class ApplicationResearchExecutionOutput(BaseModel):
    """Normalized output returned by a research runner."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    summary: str
    result: dict[str, JsonValue] = Field(
        default_factory=dict
    )
    artifact_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        """Validate normalized research output."""

        if not self.summary.strip():
            raise ValueError(
                "summary must not be blank"
            )

        self._validate_unique_text(
            self.artifact_ids,
            field_name="artifact_ids",
        )
        self._validate_unique_text(
            self.citation_ids,
            field_name="citation_ids",
        )

        return self

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate unique nonblank identifiers."""

        if any(not value.strip() for value in values):
            raise ValueError(
                f"{field_name} must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in values
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                f"{field_name} must not contain duplicates"
            )


class ApplicationResearchExecutionResult(BaseModel):
    """Successful application research execution result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    execution: ApplicationExecutionRecord
    output: ApplicationResearchExecutionOutput

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate successful execution result."""

        if not self.execution.terminal:
            raise ValueError(
                "research execution result requires "
                "terminal execution"
            )

        return self


@runtime_checkable
class ResearchExecutionRunner(Protocol):
    """Contract implemented by a concrete research executor."""

    def execute(
        self,
        request: ApplicationResearchExecutionRequest,
    ) -> ApplicationResearchExecutionOutput:
        """Execute one research request."""
