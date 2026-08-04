"""Contract and schemas for specialist source-search execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
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


class ResearchSearchExecutorError(RuntimeError):
    """Base exception raised by a research search executor."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SEARCH_EXECUTOR_ERROR",
        retryable: bool = False,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)

        if not code.strip():
            raise ValueError(
                "code must not be blank"
            )

        self.code = code
        self.retryable = retryable
        self.details = details or {}


class ResearchSearchHit(BaseModel):
    """One normalized source-search result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    title: str
    location: str
    snippet: str | None = None
    score: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    query_id: str | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_hit(self) -> Self:
        """Validate source-search result fields."""

        required_text = {
            "source_id": self.source_id,
            "title": self.title,
            "location": self.location,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_optional_text(
            self.snippet,
            field_name="snippet",
        )
        self._validate_optional_text(
            self.query_id,
            field_name="query_id",
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
    def _validate_optional_text(
        value: str | None,
        *,
        field_name: str,
    ) -> None:
        """Validate optional text when supplied."""

        if value is not None and not value.strip():
            raise ValueError(
                f"{field_name} must not be blank when provided"
            )


class ResearchSearchExecutionResult(BaseModel):
    """Normalized output from one search executor call."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    hits: list[ResearchSearchHit] = Field(
        default_factory=list
    )
    query_count: int = Field(
        default=0,
        ge=0,
    )
    tool_call_count: int = Field(
        default=1,
        ge=0,
    )
    duration_ms: int = Field(
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
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate search result identity and metadata."""

        source_ids = [
            hit.source_id.strip().casefold()
            for hit in self.hits
        ]

        if len(set(source_ids)) != len(source_ids):
            raise ValueError(
                "search hits must have unique source IDs"
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


class ResearchSearchExecutor(ABC):
    """Abstract search execution contract used by a specialist."""

    @abstractmethod
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSearchExecutionResult:
        """Execute one specialist search assignment."""
