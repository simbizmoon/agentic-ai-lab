"""Contract and schemas for specialist source criticism."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    model_validator,
)

from app.schemas.research_agent_assignment import (
    ResearchAgentTaskAssignment,
)


class ResearchSourceCriticExecutorError(RuntimeError):
    """Structured exception raised by a source critic executor."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SOURCE_CRITIC_EXECUTOR_ERROR",
        retryable: bool = False,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)

        if not code.strip():
            raise ValueError("code must not be blank")

        self.code = code
        self.retryable = retryable
        self.details = details or {}


class ResearchSourceDecision(StrEnum):
    """Deterministic source review decision."""

    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"


class ResearchSourceCritique(BaseModel):
    """Quality review of one research source."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    critique_id: str
    source_id: str
    decision: ResearchSourceDecision
    authority_score: float = Field(ge=0, le=1)
    relevance_score: float = Field(ge=0, le=1)
    recency_score: float = Field(ge=0, le=1)
    transparency_score: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    rationale: str
    concerns: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_critique(self) -> Self:
        """Validate source critique fields."""

        required_text = {
            "critique_id": self.critique_id,
            "source_id": self.source_id,
            "rationale": self.rationale,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_unique_text(
            self.concerns,
            field_name="concerns",
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

    @staticmethod
    def _validate_unique_text(
        values: list[str],
        *,
        field_name: str,
    ) -> None:
        """Validate nonblank unique text entries."""

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


class ResearchSourceCriticFailure(BaseModel):
    """Failure to review one source."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    code: str
    message: str
    retryable: bool = False

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate source-level review failure."""

        for field_name, value in {
            "source_id": self.source_id,
            "code": self.code,
            "message": self.message,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class ResearchSourceCriticExecutionResult(BaseModel):
    """Normalized result from source criticism."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    requested_source_count: int = Field(ge=0)
    critiques: list[ResearchSourceCritique] = Field(
        default_factory=list
    )
    failures: list[ResearchSourceCriticFailure] = Field(
        default_factory=list
    )
    tool_call_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    input_token_count: int = Field(default=0, ge=0)
    output_token_count: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate source review accounting."""

        critique_ids = [
            item.critique_id.strip().casefold()
            for item in self.critiques
        ]

        if len(set(critique_ids)) != len(critique_ids):
            raise ValueError(
                "critiques must have unique critique IDs"
            )

        reviewed_source_ids = [
            item.source_id.strip().casefold()
            for item in self.critiques
        ]

        if len(set(reviewed_source_ids)) != len(
            reviewed_source_ids
        ):
            raise ValueError(
                "critiques must have unique source IDs"
            )

        failed_source_ids = [
            item.source_id.strip().casefold()
            for item in self.failures
        ]

        if len(set(failed_source_ids)) != len(
            failed_source_ids
        ):
            raise ValueError(
                "failures must have unique source IDs"
            )

        if set(reviewed_source_ids) & set(
            failed_source_ids
        ):
            raise ValueError(
                "source must not appear in both "
                "critiques and failures"
            )

        if (
            len(reviewed_source_ids)
            + len(failed_source_ids)
            > self.requested_source_count
        ):
            raise ValueError(
                "reviewed sources and failures must not "
                "exceed requested_source_count"
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

    @property
    def reviewed_source_count(self) -> int:
        """Return successfully reviewed source count."""

        return len(self.critiques)

    @property
    def failed_source_count(self) -> int:
        """Return source review failure count."""

        return len(self.failures)

    @property
    def is_complete(self) -> bool:
        """Return whether all requested sources were reviewed."""

        return (
            self.reviewed_source_count
            == self.requested_source_count
            and not self.failures
        )


class ResearchSourceCriticExecutor(ABC):
    """Abstract source criticism execution contract."""

    @abstractmethod
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceCriticExecutionResult:
        """Review source quality for one assignment."""
