"""Schemas for deterministic research request validation."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ResearchRequestValidationSeverity(StrEnum):
    """Severity of one research request validation issue."""

    ERROR = "error"
    WARNING = "warning"


class ResearchRequestValidationCode(StrEnum):
    """Stable code for one research request issue."""

    QUESTION_TOO_SHORT = "question_too_short"
    OBJECTIVE_TOO_SHORT = "objective_too_short"
    QUESTION_OBJECTIVE_DUPLICATE = (
        "question_objective_duplicate"
    )
    DEEP_RESEARCH_REQUIRES_CITATIONS = (
        "deep_research_requires_citations"
    )
    DEEP_RESEARCH_REQUIRES_MORE_SOURCES = (
        "deep_research_requires_more_sources"
    )
    NO_PREFERRED_SOURCE_TYPES = (
        "no_preferred_source_types"
    )
    NO_INCLUDED_TOPICS = "no_included_topics"
    QUICK_RESEARCH_HIGH_SOURCE_LIMIT = (
        "quick_research_high_source_limit"
    )
    CITATIONS_NOT_REQUIRED = "citations_not_required"


class ResearchRequestValidationIssue(BaseModel):
    """One deterministic research request validation issue."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    code: ResearchRequestValidationCode
    severity: ResearchRequestValidationSeverity
    field: str
    message: str

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        """Validate issue text fields."""

        if not self.field.strip():
            raise ValueError(
                "field must not be blank"
            )

        if not self.message.strip():
            raise ValueError(
                "message must not be blank"
            )

        return self


class ResearchRequestValidationResult(BaseModel):
    """Combined readiness validation result."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    request_id: str
    valid: bool
    issues: list[ResearchRequestValidationIssue] = Field(
        default_factory=list
    )
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        """Validate counts and readiness state."""

        if not self.request_id.strip():
            raise ValueError(
                "request_id must not be blank"
            )

        actual_error_count = sum(
            issue.severity
            is ResearchRequestValidationSeverity.ERROR
            for issue in self.issues
        )
        actual_warning_count = sum(
            issue.severity
            is ResearchRequestValidationSeverity.WARNING
            for issue in self.issues
        )

        if self.error_count != actual_error_count:
            raise ValueError(
                "error_count must match validation issues"
            )

        if self.warning_count != actual_warning_count:
            raise ValueError(
                "warning_count must match validation issues"
            )

        if self.valid != (actual_error_count == 0):
            raise ValueError(
                "valid must be true exactly when "
                "there are no errors"
            )

        issue_keys = [
            (
                issue.code,
                issue.severity,
                issue.field,
            )
            for issue in self.issues
        ]

        if len(set(issue_keys)) != len(issue_keys):
            raise ValueError(
                "validation issues must not contain "
                "duplicates"
            )

        return self
