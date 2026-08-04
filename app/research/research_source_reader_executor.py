"""Contract and schemas for specialist source-reading execution."""

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


class ResearchSourceReaderExecutorError(RuntimeError):
    """Structured exception raised by a source reader executor."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "SOURCE_READER_EXECUTOR_ERROR",
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


class ResearchReadDocument(BaseModel):
    """One normalized document read from a source."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    document_id: str
    source_id: str
    title: str
    content: str
    location: str | None = None
    content_type: str = "text/plain"
    word_count: int = Field(
        default=0,
        ge=0,
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        """Validate normalized document content."""

        required_text = {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "title": self.title,
            "content": self.content,
            "content_type": self.content_type,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.location is not None
            and not self.location.strip()
        ):
            raise ValueError(
                "location must not be blank when provided"
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


class ResearchSourceReadFailure(BaseModel):
    """Failure to read one individual source."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    source_id: str
    code: str
    message: str
    retryable: bool = False
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate individual source failure."""

        required_text = {
            "source_id": self.source_id,
            "code": self.code,
            "message": self.message,
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


class ResearchSourceReaderExecutionResult(BaseModel):
    """Normalized result from one source reader execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    requested_source_count: int = Field(
        ge=0
    )
    documents: list[ResearchReadDocument] = Field(
        default_factory=list
    )
    failures: list[ResearchSourceReadFailure] = Field(
        default_factory=list
    )
    tool_call_count: int = Field(
        default=0,
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
        """Validate document and failure consistency."""

        document_source_ids = [
            document.source_id.strip().casefold()
            for document in self.documents
        ]

        if len(set(document_source_ids)) != len(
            document_source_ids
        ):
            raise ValueError(
                "documents must have unique source IDs"
            )

        failure_source_ids = [
            failure.source_id.strip().casefold()
            for failure in self.failures
        ]

        if len(set(failure_source_ids)) != len(
            failure_source_ids
        ):
            raise ValueError(
                "failures must have unique source IDs"
            )

        if set(document_source_ids) & set(
            failure_source_ids
        ):
            raise ValueError(
                "source must not appear in both "
                "documents and failures"
            )

        completed_count = (
            len(self.documents)
            + len(self.failures)
        )

        if completed_count > self.requested_source_count:
            raise ValueError(
                "documents and failures must not exceed "
                "requested_source_count"
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
    def successful_source_count(self) -> int:
        """Return the number of successfully read sources."""

        return len(self.documents)

    @property
    def failed_source_count(self) -> int:
        """Return the number of failed source reads."""

        return len(self.failures)

    @property
    def is_complete(self) -> bool:
        """Return whether every requested source was read."""

        return (
            self.requested_source_count
            == len(self.documents)
            and not self.failures
        )


class ResearchSourceReaderExecutor(ABC):
    """Abstract source-reading execution contract."""

    @abstractmethod
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchSourceReaderExecutionResult:
        """Read sources for one specialist assignment."""
