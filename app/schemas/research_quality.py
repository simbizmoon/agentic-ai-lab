"""Schemas for final research report quality evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.research_synthesis import (
    ResearchSynthesisReport,
)


class ResearchQualityLevel(StrEnum):
    """Overall quality level of a research report."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXCELLENT = "excellent"


class ResearchQualityIssueSeverity(StrEnum):
    """Severity of one research quality issue."""

    WARNING = "warning"
    ERROR = "error"


class ResearchQualityIssueCode(StrEnum):
    """Machine-readable research quality issue code."""

    MISSING_CLAIMS = "missing_claims"
    UNCITED_CLAIMS = "uncited_claims"
    LOW_SOURCE_DIVERSITY = "low_source_diversity"
    LOW_SOURCE_QUALITY = "low_source_quality"
    UNHANDLED_CONTRADICTIONS = "unhandled_contradictions"


class ResearchQualityIssue(BaseModel):
    """One structured quality issue."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    code: ResearchQualityIssueCode
    severity: ResearchQualityIssueSeverity
    message: str
    related_ids: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        """Validate issue message and related IDs."""

        if not self.message.strip():
            raise ValueError(
                "message must not be blank"
            )

        if any(
            not value.strip()
            for value in self.related_ids
        ):
            raise ValueError(
                "related_ids must not contain blank values"
            )

        normalized = [
            value.strip().casefold()
            for value in self.related_ids
        ]

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "related_ids must not contain duplicates"
            )

        return self


class ResearchQualityEvaluation(BaseModel):
    """Final quality assessment of a synthesized report."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    report: ResearchSynthesisReport
    evaluator: str
    claim_coverage_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    citation_coverage_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    source_diversity_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    source_quality_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    contradiction_handling_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    overall_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    quality_level: ResearchQualityLevel
    issues: list[ResearchQualityIssue] = Field(
        default_factory=list
    )
    metadata: dict[str, str] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        """Validate evaluation identity and score level."""

        if not self.evaluator.strip():
            raise ValueError(
                "evaluator must not be blank"
            )

        expected_level = self.level_for_score(
            self.overall_score
        )

        if self.quality_level is not expected_level:
            raise ValueError(
                "quality_level must match overall_score"
            )

        issue_keys = [
            (
                issue.code,
                tuple(
                    value.strip().casefold()
                    for value in issue.related_ids
                ),
            )
            for issue in self.issues
        ]

        if len(set(issue_keys)) != len(issue_keys):
            raise ValueError(
                "quality issues must not contain duplicates"
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
    def level_for_score(
        score: float,
    ) -> ResearchQualityLevel:
        """Return a quality level for one overall score."""

        if score >= 0.90:
            return ResearchQualityLevel.EXCELLENT

        if score >= 0.75:
            return ResearchQualityLevel.HIGH

        if score >= 0.50:
            return ResearchQualityLevel.MEDIUM

        return ResearchQualityLevel.LOW

    @property
    def passed(self) -> bool:
        """Return whether the evaluation has no error issues."""

        return not any(
            issue.severity
            is ResearchQualityIssueSeverity.ERROR
            for issue in self.issues
        )
