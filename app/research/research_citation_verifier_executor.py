"""Contract and schemas for citation verification."""

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


class ResearchCitationVerifierExecutorError(RuntimeError):
    """Structured exception raised by a citation verifier."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CITATION_VERIFIER_EXECUTOR_ERROR",
        retryable: bool = False,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)

        if not code.strip():
            raise ValueError("code must not be blank")

        self.code = code
        self.retryable = retryable
        self.details = details or {}


class ResearchCitationDecision(StrEnum):
    """Citation verification decision."""

    VERIFIED = "verified"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


class ResearchCitationVerification(BaseModel):
    """Verification result for one claim and citation pair."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    verification_id: str
    claim_id: str
    citation_id: str
    evidence_id: str
    source_id: str
    decision: ResearchCitationDecision
    entailment_score: float = Field(ge=0, le=1)
    traceability_score: float = Field(ge=0, le=1)
    citation_accuracy_score: float = Field(ge=0, le=1)
    rationale: str
    issues: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_verification(self) -> Self:
        """Validate citation verification identity."""

        required_text = {
            "verification_id": self.verification_id,
            "claim_id": self.claim_id,
            "citation_id": self.citation_id,
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "rationale": self.rationale,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        if any(not issue.strip() for issue in self.issues):
            raise ValueError(
                "issues must not contain blank values"
            )

        normalized_issues = [
            issue.strip().casefold()
            for issue in self.issues
        ]

        if len(set(normalized_issues)) != len(
            normalized_issues
        ):
            raise ValueError(
                "issues must not contain duplicates"
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


class ResearchCitationVerificationFailure(BaseModel):
    """Failure to verify one citation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    citation_id: str
    code: str
    message: str
    retryable: bool = False

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        """Validate citation-level failure."""

        for field_name, value in {
            "citation_id": self.citation_id,
            "code": self.code,
            "message": self.message,
        }.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        return self


class ResearchCitationVerifierExecutionResult(BaseModel):
    """Normalized citation verification result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    requested_citation_count: int = Field(ge=0)
    verifications: list[
        ResearchCitationVerification
    ] = Field(default_factory=list)
    failures: list[
        ResearchCitationVerificationFailure
    ] = Field(default_factory=list)
    tool_call_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    input_token_count: int = Field(default=0, ge=0)
    output_token_count: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate citation verification accounting."""

        verification_ids = [
            item.verification_id.strip().casefold()
            for item in self.verifications
        ]

        if len(set(verification_ids)) != len(
            verification_ids
        ):
            raise ValueError(
                "verifications must have unique "
                "verification IDs"
            )

        verified_citation_ids = [
            item.citation_id.strip().casefold()
            for item in self.verifications
        ]

        if len(set(verified_citation_ids)) != len(
            verified_citation_ids
        ):
            raise ValueError(
                "verifications must have unique citation IDs"
            )

        failed_citation_ids = [
            item.citation_id.strip().casefold()
            for item in self.failures
        ]

        if len(set(failed_citation_ids)) != len(
            failed_citation_ids
        ):
            raise ValueError(
                "failures must have unique citation IDs"
            )

        if set(verified_citation_ids) & set(
            failed_citation_ids
        ):
            raise ValueError(
                "citation must not appear in both "
                "verifications and failures"
            )

        if (
            len(verified_citation_ids)
            + len(failed_citation_ids)
            > self.requested_citation_count
        ):
            raise ValueError(
                "verified citations and failures must not "
                "exceed requested_citation_count"
            )

        return self

    @property
    def verified_citation_count(self) -> int:
        """Return successfully checked citation count."""

        return len(self.verifications)

    @property
    def failed_citation_count(self) -> int:
        """Return citation verification failure count."""

        return len(self.failures)

    @property
    def is_complete(self) -> bool:
        """Return whether all citations were checked."""

        return (
            self.verified_citation_count
            == self.requested_citation_count
            and not self.failures
        )


class ResearchCitationVerifierExecutor(ABC):
    """Abstract citation verification execution contract."""

    @abstractmethod
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchCitationVerifierExecutionResult:
        """Verify citations for one specialist assignment."""
