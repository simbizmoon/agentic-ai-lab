"""Contract and schemas for specialist evidence extraction."""

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


class ResearchEvidenceExecutorError(RuntimeError):
    """Structured exception raised by an evidence executor."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "EVIDENCE_EXECUTOR_ERROR",
        retryable: bool = False,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)

        if not code.strip():
            raise ValueError("code must not be blank")

        self.code = code
        self.retryable = retryable
        self.details = details or {}


class ResearchExtractedEvidence(BaseModel):
    """One normalized evidence item extracted from a document."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evidence_id: str
    document_id: str
    source_id: str
    text: str
    interpretation: str
    relevance_score: float = Field(
        ge=0,
        le=1,
    )
    confidence_score: float = Field(
        ge=0,
        le=1,
    )
    location_reference: str | None = None
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        """Validate evidence identity and traceability."""

        required_text = {
            "evidence_id": self.evidence_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "text": self.text,
            "interpretation": self.interpretation,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if (
            self.location_reference is not None
            and not self.location_reference.strip()
        ):
            raise ValueError(
                "location_reference must not be blank "
                "when provided"
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


class ResearchEvidenceDocumentFailure(BaseModel):
    """Failure to extract evidence from one document."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    document_id: str
    source_id: str
    code: str
    message: str
    retryable: bool = False

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate document-level extraction failure."""

        required_text = {
            "document_id": self.document_id,
            "source_id": self.source_id,
            "code": self.code,
            "message": self.message,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class ResearchEvidenceExecutionResult(BaseModel):
    """Normalized result from one evidence extraction execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    requested_document_count: int = Field(ge=0)
    evidence: list[ResearchExtractedEvidence] = Field(
        default_factory=list
    )
    failures: list[
        ResearchEvidenceDocumentFailure
    ] = Field(default_factory=list)
    tool_call_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    input_token_count: int = Field(default=0, ge=0)
    output_token_count: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate evidence identity and document accounting."""

        evidence_ids = [
            item.evidence_id.strip().casefold()
            for item in self.evidence
        ]

        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError(
                "evidence items must have unique evidence IDs"
            )

        failed_document_ids = [
            failure.document_id.strip().casefold()
            for failure in self.failures
        ]

        if len(set(failed_document_ids)) != len(
            failed_document_ids
        ):
            raise ValueError(
                "failures must have unique document IDs"
            )

        successful_document_ids = {
            item.document_id.strip().casefold()
            for item in self.evidence
        }

        if successful_document_ids & set(
            failed_document_ids
        ):
            raise ValueError(
                "document must not appear in both "
                "evidence and failures"
            )

        accounted_documents = (
            len(successful_document_ids)
            + len(failed_document_ids)
        )

        if accounted_documents > self.requested_document_count:
            raise ValueError(
                "accounted documents must not exceed "
                "requested_document_count"
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
    def evidence_count(self) -> int:
        """Return extracted evidence item count."""

        return len(self.evidence)

    @property
    def failed_document_count(self) -> int:
        """Return failed document count."""

        return len(self.failures)

    @property
    def successful_document_count(self) -> int:
        """Return count of documents producing evidence."""

        return len({
            item.document_id
            for item in self.evidence
        })

    @property
    def is_complete(self) -> bool:
        """Return whether all documents produced evidence."""

        return (
            self.successful_document_count
            == self.requested_document_count
            and not self.failures
        )


class ResearchEvidenceExecutor(ABC):
    """Abstract evidence extraction execution contract."""

    @abstractmethod
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchEvidenceExecutionResult:
        """Extract evidence for one specialist assignment."""
