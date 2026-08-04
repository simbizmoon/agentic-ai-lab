"""Contract and schemas for independent research quality review."""

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


class ResearchQualityReviewExecutorError(RuntimeError):
    """Structured exception raised by a quality review executor."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "QUALITY_REVIEW_EXECUTOR_ERROR",
        retryable: bool = False,
        details: dict[str, JsonValue] | None = None,
    ) -> None:
        super().__init__(message)

        if not code.strip():
            raise ValueError("code must not be blank")

        self.code = code
        self.retryable = retryable
        self.details = details or {}


class ResearchQualityDecision(StrEnum):
    """Final decision from an independent quality review."""

    APPROVED = "approved"
    REVISION_REQUIRED = "revision_required"
    REJECTED = "rejected"


class ResearchRevisionSeverity(StrEnum):
    """Severity assigned to one requested revision."""

    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class ResearchRevisionRequest(BaseModel):
    """One concrete change requested by a quality reviewer."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    revision_id: str
    target_type: str
    target_id: str
    issue: str
    required_action: str
    severity: ResearchRevisionSeverity
    required: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_revision(self) -> Self:
        """Validate revision identity and requested action."""

        required_text = {
            "revision_id": self.revision_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "issue": self.issue,
            "required_action": self.required_action,
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


class ResearchQualityScores(BaseModel):
    """Normalized quality scores for a research report."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    completeness: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(ge=0, le=1)
    citation_quality: float = Field(ge=0, le=1)
    source_quality: float = Field(ge=0, le=1)
    logical_consistency: float = Field(ge=0, le=1)
    clarity: float = Field(ge=0, le=1)

    @property
    def overall_score(self) -> float:
        """Return the arithmetic mean of all quality dimensions."""

        values = (
            self.completeness,
            self.evidence_coverage,
            self.citation_quality,
            self.source_quality,
            self.logical_consistency,
            self.clarity,
        )

        return sum(values) / len(values)


class ResearchQualityReview(BaseModel):
    """One complete independent report-quality evaluation."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    review_id: str
    report_id: str
    decision: ResearchQualityDecision
    scores: ResearchQualityScores
    summary: str
    strengths: list[str] = Field(default_factory=list)
    revision_requests: list[
        ResearchRevisionRequest
    ] = Field(default_factory=list)
    rejection_reason: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_review(self) -> Self:
        """Validate review decision and revision semantics."""

        required_text = {
            "review_id": self.review_id,
            "report_id": self.report_id,
            "summary": self.summary,
        }

        for field_name, value in required_text.items():
            if not value.strip():
                raise ValueError(
                    f"{field_name} must not be blank"
                )

        self._validate_unique_text(
            self.strengths,
            field_name="strengths",
        )

        revision_ids = [
            revision.revision_id.strip().casefold()
            for revision in self.revision_requests
        ]

        if len(set(revision_ids)) != len(revision_ids):
            raise ValueError(
                "revision requests must have unique revision IDs"
            )

        if (
            self.rejection_reason is not None
            and not self.rejection_reason.strip()
        ):
            raise ValueError(
                "rejection_reason must not be blank when provided"
            )

        required_revisions = [
            revision
            for revision in self.revision_requests
            if revision.required
        ]

        if self.decision is ResearchQualityDecision.APPROVED:
            if required_revisions:
                raise ValueError(
                    "approved review must not include "
                    "required revisions"
                )

            if self.rejection_reason is not None:
                raise ValueError(
                    "approved review must not include "
                    "rejection_reason"
                )

        if (
            self.decision
            is ResearchQualityDecision.REVISION_REQUIRED
        ):
            if not required_revisions:
                raise ValueError(
                    "revision-required review must include "
                    "a required revision"
                )

            if self.rejection_reason is not None:
                raise ValueError(
                    "revision-required review must not include "
                    "rejection_reason"
                )

        if (
            self.decision is ResearchQualityDecision.REJECTED
            and self.rejection_reason is None
        ):
            raise ValueError(
                "rejected review must include "
                "rejection_reason"
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

    @property
    def approved(self) -> bool:
        """Return whether the report passed quality review."""

        return self.decision is ResearchQualityDecision.APPROVED

    @property
    def requires_revision(self) -> bool:
        """Return whether the report must be revised."""

        return (
            self.decision
            is ResearchQualityDecision.REVISION_REQUIRED
        )


class ResearchQualityReviewExecutionResult(BaseModel):
    """Normalized output from one quality review execution."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    review: ResearchQualityReview | None = None
    tool_call_count: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    input_token_count: int = Field(default=0, ge=0)
    output_token_count: int = Field(default=0, ge=0)
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate execution metadata."""

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


class ResearchQualityReviewExecutor(ABC):
    """Abstract independent report-quality review contract."""

    @abstractmethod
    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        """Evaluate one synthesized research report."""
