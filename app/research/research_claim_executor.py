"""Contract and schemas for evidence-based claim construction."""

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


class ResearchClaimExecutorError(RuntimeError):
    """Structured exception raised by a claim executor."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CLAIM_EXECUTOR_ERROR",
        retryable: bool = False,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)

        if not code.strip():
            raise ValueError("code must not be blank")

        self.code = code
        self.retryable = retryable
        self.details = details or {}


class ResearchConstructedCitation(BaseModel):
    """Citation connecting a claim to evidence and source."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    citation_id: str
    evidence_id: str
    source_id: str
    document_id: str
    location_reference: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_citation(self) -> Self:
        """Validate citation traceability."""

        required_text = {
            "citation_id": self.citation_id,
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "document_id": self.document_id,
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


class ResearchConstructedClaim(BaseModel):
    """One claim constructed from traceable evidence."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    claim_id: str
    text: str
    rationale: str
    confidence_score: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)
    citations: list[ResearchConstructedCitation] = Field(
        min_length=1
    )
    qualifications: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        """Validate claim identity and evidence references."""

        for field_name, value in {
            "claim_id": self.claim_id,
            "text": self.text,
            "rationale": self.rationale,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_unique_text(
            self.evidence_ids,
            field_name="evidence_ids",
        )
        self._validate_unique_text(
            self.qualifications,
            field_name="qualifications",
        )

        citation_ids = [
            citation.citation_id.strip().casefold()
            for citation in self.citations
        ]

        if len(set(citation_ids)) != len(citation_ids):
            raise ValueError(
                "citations must have unique citation IDs"
            )

        referenced_evidence = {
            citation.evidence_id.strip().casefold()
            for citation in self.citations
        }
        declared_evidence = {
            evidence_id.strip().casefold()
            for evidence_id in self.evidence_ids
        }

        if not referenced_evidence.issubset(
            declared_evidence
        ):
            raise ValueError(
                "citation evidence must appear in evidence_ids"
            )

        if not declared_evidence.issubset(
            referenced_evidence
        ):
            raise ValueError(
                "every evidence_id must have a citation"
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
        """Validate nonblank unique text values."""

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


class ResearchClaimConstructionFailure(BaseModel):
    """Failure to construct a claim from one evidence group."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    evidence_group_id: str
    code: str
    message: str
    retryable: bool = False

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate claim-construction failure."""

        for field_name, value in {
            "evidence_group_id": self.evidence_group_id,
            "code": self.code,
            "message": self.message,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class ResearchClaimExecutionResult(BaseModel):
    """Normalized claim construction result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    requested_evidence_group_count: int = Field(ge=0)
    claims: list[ResearchConstructedClaim] = Field(
        default_factory=list
    )
    failures: list[
        ResearchClaimConstructionFailure
    ] = Field(default_factory=list)
    tool_call_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    input_token_count: int = Field(default=0, ge=0)
    output_token_count: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate claim result identity and accounting."""

        claim_ids = [
            claim.claim_id.strip().casefold()
            for claim in self.claims
        ]

        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError(
                "claims must have unique claim IDs"
            )

        citation_ids = [
            citation.citation_id.strip().casefold()
            for claim in self.claims
            for citation in claim.citations
        ]

        if len(set(citation_ids)) != len(citation_ids):
            raise ValueError(
                "claims must have globally unique citation IDs"
            )

        failure_ids = [
            failure.evidence_group_id.strip().casefold()
            for failure in self.failures
        ]

        if len(set(failure_ids)) != len(failure_ids):
            raise ValueError(
                "failures must have unique evidence group IDs"
            )

        if (
            len(self.claims) + len(self.failures)
            > self.requested_evidence_group_count
        ):
            raise ValueError(
                "claims and failures must not exceed "
                "requested_evidence_group_count"
            )

        return self

    @property
    def claim_count(self) -> int:
        """Return constructed claim count."""

        return len(self.claims)

    @property
    def failed_group_count(self) -> int:
        """Return failed evidence-group count."""

        return len(self.failures)

    @property
    def is_complete(self) -> bool:
        """Return whether all evidence groups produced claims."""

        return (
            self.claim_count
            == self.requested_evidence_group_count
            and not self.failures
        )


class ResearchClaimExecutor(ABC):
    """Abstract evidence-to-claim execution contract."""

    @abstractmethod
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchClaimExecutionResult:
        """Construct claims for one specialist assignment."""
