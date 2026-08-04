"""Schemas for research-agent task results and failures."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.schemas.research_agent import (
    ResearchAgentIdentity,
)
from app.schemas.research_agent_assignment import (
    ResearchAgentTaskAssignment,
)


class ResearchAgentResultStatus(StrEnum):
    """Outcome status of one agent task execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class ResearchAgentFailureCategory(StrEnum):
    """High-level failure category for an agent execution."""

    VALIDATION = "validation"
    PERMISSION = "permission"
    TOOL = "tool"
    SOURCE = "source"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    DEPENDENCY = "dependency"
    INTERNAL = "internal"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class ResearchAgentOutputReference(BaseModel):
    """Reference to one structured result artifact."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    name: str
    output_type: str
    reference_id: str
    primary: bool = False
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_output_reference(self) -> Self:
        """Validate output identity and metadata."""

        required_text = {
            "name": self.name,
            "output_type": self.output_type,
            "reference_id": self.reference_id,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
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


class ResearchAgentExecutionMetrics(BaseModel):
    """Deterministic execution metrics for one agent result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    duration_ms: int = Field(
        default=0,
        ge=0,
    )
    tool_call_count: int = Field(
        default=0,
        ge=0,
    )
    input_token_count: int = Field(
        default=0,
        ge=0,
    )
    output_token_count: int = Field(
        default=0,
        ge=0,
    )
    source_count: int = Field(
        default=0,
        ge=0,
    )
    evidence_count: int = Field(
        default=0,
        ge=0,
    )
    claim_count: int = Field(
        default=0,
        ge=0,
    )

    @property
    def total_token_count(self) -> int:
        """Return combined input and output token count."""

        return (
            self.input_token_count
            + self.output_token_count
        )


class ResearchAgentFailure(BaseModel):
    """Structured failure information from an agent execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    category: ResearchAgentFailureCategory
    code: str
    message: str
    retryable: bool = False
    retry_reason: str | None = None
    failed_stage: str | None = None
    details: dict[str, JsonValue] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate failure identity and retry semantics."""

        if not self.code.strip():
            raise ValueError(
                "failure code must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "failure message must not be blank"
            )

        self._validate_optional_text(
            self.retry_reason,
            field_name="retry_reason",
        )
        self._validate_optional_text(
            self.failed_stage,
            field_name="failed_stage",
        )

        if self.retryable and self.retry_reason is None:
            raise ValueError(
                "retryable failure must include retry_reason"
            )

        if (
            not self.retryable
            and self.retry_reason is not None
        ):
            raise ValueError(
                "non-retryable failure must not include "
                "retry_reason"
            )

        if any(
            not key.strip()
            for key in self.details
        ):
            raise ValueError(
                "failure detail keys must not be blank"
            )

        return self

    @staticmethod
    def _validate_optional_text(
        value: str | None,
        *,
        field_name: str,
    ) -> None:
        """Validate one optional text field."""

        if value is not None and not value.strip():
            raise ValueError(
                f"{field_name} must not be blank when provided"
            )


class ResearchAgentTaskResult(BaseModel):
    """Immutable outcome of one research-agent assignment."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    result_id: str
    assignment: ResearchAgentTaskAssignment
    agent: ResearchAgentIdentity
    status: ResearchAgentResultStatus
    summary: str
    outputs: list[
        ResearchAgentOutputReference
    ] = Field(default_factory=list)
    payload: dict[str, JsonValue] = Field(
        default_factory=dict
    )
    metrics: ResearchAgentExecutionMetrics = Field(
        default_factory=ResearchAgentExecutionMetrics
    )
    failure: ResearchAgentFailure | None = None
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate assignment, agent, outcome, and outputs."""

        if not self.result_id.strip():
            raise ValueError(
                "result_id must not be blank"
            )

        if not self.summary.strip():
            raise ValueError(
                "summary must not be blank"
            )

        if (
            self.agent.agent_id.strip().casefold()
            != self.assignment.assignee.agent_id
            .strip()
            .casefold()
        ):
            raise ValueError(
                "result agent must match assignment assignee"
            )

        self._validate_outputs()
        self._validate_status_semantics()
        self._validate_retry_semantics()
        self._validate_payload()
        self._validate_metadata()

        return self

    def _validate_outputs(self) -> None:
        """Validate output references and primary output."""

        output_keys = [
            (
                output.output_type.strip().casefold(),
                output.reference_id.strip().casefold(),
            )
            for output in self.outputs
        ]

        if len(set(output_keys)) != len(output_keys):
            raise ValueError(
                "outputs must not contain duplicate references"
            )

        primary_count = sum(
            output.primary
            for output in self.outputs
        )

        if primary_count > 1:
            raise ValueError(
                "result must not contain multiple primary outputs"
            )

    def _validate_status_semantics(self) -> None:
        """Validate required output and failure combinations."""

        if (
            self.status
            is ResearchAgentResultStatus.SUCCEEDED
        ):
            if not self.outputs:
                raise ValueError(
                    "successful result must include output"
                )

            if self.failure is not None:
                raise ValueError(
                    "successful result must not include failure"
                )

        elif (
            self.status
            is ResearchAgentResultStatus.FAILED
        ):
            if self.failure is None:
                raise ValueError(
                    "failed result must include failure"
                )

            if self.outputs:
                raise ValueError(
                    "failed result must not include outputs"
                )

        elif (
            self.status
            is ResearchAgentResultStatus.CANCELLED
        ):
            if self.failure is None:
                raise ValueError(
                    "cancelled result must include failure"
                )

            if (
                self.failure.category
                is not ResearchAgentFailureCategory.CANCELLED
            ):
                raise ValueError(
                    "cancelled result failure category "
                    "must be cancelled"
                )

        elif (
            self.status
            is ResearchAgentResultStatus.PARTIAL
        ):
            if not self.outputs:
                raise ValueError(
                    "partial result must include output"
                )

            if self.failure is None:
                raise ValueError(
                    "partial result must include failure"
                )

    def _validate_retry_semantics(self) -> None:
        """Validate retry recommendation against assignment attempts."""

        if (
            self.failure is not None
            and self.failure.retryable
            and self.assignment.attempt_number
            >= self.assignment.maximum_attempts
        ):
            raise ValueError(
                "retryable failure requires remaining attempts"
            )

    def _validate_payload(self) -> None:
        """Validate result payload keys."""

        if any(
            not key.strip()
            for key in self.payload
        ):
            raise ValueError(
                "payload keys must not be blank"
            )

    def _validate_metadata(self) -> None:
        """Validate result metadata."""

        for key, value in self.metadata.items():
            if not key.strip():
                raise ValueError(
                    "metadata keys must not be blank"
                )

            if not value.strip():
                raise ValueError(
                    "metadata values must not be blank"
                )

    @property
    def succeeded(self) -> bool:
        """Return whether the task completed successfully."""

        return (
            self.status
            is ResearchAgentResultStatus.SUCCEEDED
        )

    @property
    def can_retry(self) -> bool:
        """Return whether another execution attempt is allowed."""

        return (
            self.failure is not None
            and self.failure.retryable
            and self.assignment.attempt_number
            < self.assignment.maximum_attempts
        )

    def primary_output(
        self,
    ) -> ResearchAgentOutputReference | None:
        """Return the explicitly primary output or the only output."""

        explicit = next(
            (
                output
                for output in self.outputs
                if output.primary
            ),
            None,
        )

        if explicit is not None:
            return explicit

        if len(self.outputs) == 1:
            return self.outputs[0]

        return None
