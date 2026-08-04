"""Deterministic readiness validation for research requests."""

from __future__ import annotations

from app.schemas.research_request import (
    ResearchDepth,
    ResearchRequest,
)
from app.schemas.research_request_validation import (
    ResearchRequestValidationCode,
    ResearchRequestValidationIssue,
    ResearchRequestValidationResult,
    ResearchRequestValidationSeverity,
)


class ResearchRequestValidator:
    """Evaluate whether a research request is ready to run."""

    MINIMUM_QUESTION_LENGTH = 10
    MINIMUM_OBJECTIVE_LENGTH = 15
    MINIMUM_DEEP_RESEARCH_SOURCES = 5
    QUICK_RESEARCH_SOURCE_WARNING_LIMIT = 20

    def validate(
        self,
        request: ResearchRequest,
    ) -> ResearchRequestValidationResult:
        """Return deterministic validation issues."""

        issues: list[
            ResearchRequestValidationIssue
        ] = []

        self._validate_question(
            request=request,
            issues=issues,
        )
        self._validate_objective(
            request=request,
            issues=issues,
        )
        self._validate_distinct_purpose(
            request=request,
            issues=issues,
        )
        self._validate_depth(
            request=request,
            issues=issues,
        )
        self._validate_research_scope(
            request=request,
            issues=issues,
        )
        self._validate_citation_preference(
            request=request,
            issues=issues,
        )

        error_count = sum(
            issue.severity
            is ResearchRequestValidationSeverity.ERROR
            for issue in issues
        )
        warning_count = sum(
            issue.severity
            is ResearchRequestValidationSeverity.WARNING
            for issue in issues
        )

        return ResearchRequestValidationResult(
            request_id=request.request_id,
            valid=error_count == 0,
            issues=issues,
            error_count=error_count,
            warning_count=warning_count,
        )

    def _validate_question(
        self,
        *,
        request: ResearchRequest,
        issues: list[ResearchRequestValidationIssue],
    ) -> None:
        """Check whether the research question is specific enough."""

        if len(request.question.strip()) < (
            self.MINIMUM_QUESTION_LENGTH
        ):
            issues.append(
                self._issue(
                    code=(
                        ResearchRequestValidationCode
                        .QUESTION_TOO_SHORT
                    ),
                    severity=(
                        ResearchRequestValidationSeverity.ERROR
                    ),
                    field="question",
                    message=(
                        "Research question must contain at least "
                        f"{self.MINIMUM_QUESTION_LENGTH} "
                        "non-whitespace characters."
                    ),
                )
            )

    def _validate_objective(
        self,
        *,
        request: ResearchRequest,
        issues: list[ResearchRequestValidationIssue],
    ) -> None:
        """Check whether the research objective is actionable."""

        if len(request.objective.strip()) < (
            self.MINIMUM_OBJECTIVE_LENGTH
        ):
            issues.append(
                self._issue(
                    code=(
                        ResearchRequestValidationCode
                        .OBJECTIVE_TOO_SHORT
                    ),
                    severity=(
                        ResearchRequestValidationSeverity.ERROR
                    ),
                    field="objective",
                    message=(
                        "Research objective must contain at least "
                        f"{self.MINIMUM_OBJECTIVE_LENGTH} "
                        "non-whitespace characters."
                    ),
                )
            )

    def _validate_distinct_purpose(
        self,
        *,
        request: ResearchRequest,
        issues: list[ResearchRequestValidationIssue],
    ) -> None:
        """Reject a duplicated question and objective."""

        normalized_question = self._normalize(
            request.question
        )
        normalized_objective = self._normalize(
            request.objective
        )

        if normalized_question == normalized_objective:
            issues.append(
                self._issue(
                    code=(
                        ResearchRequestValidationCode
                        .QUESTION_OBJECTIVE_DUPLICATE
                    ),
                    severity=(
                        ResearchRequestValidationSeverity.ERROR
                    ),
                    field="objective",
                    message=(
                        "Research objective must explain the "
                        "desired outcome instead of repeating "
                        "the research question."
                    ),
                )
            )

    def _validate_depth(
        self,
        *,
        request: ResearchRequest,
        issues: list[ResearchRequestValidationIssue],
    ) -> None:
        """Apply readiness rules based on research depth."""

        if request.depth is ResearchDepth.DEEP:
            if not request.require_citations:
                issues.append(
                    self._issue(
                        code=(
                            ResearchRequestValidationCode
                            .DEEP_RESEARCH_REQUIRES_CITATIONS
                        ),
                        severity=(
                            ResearchRequestValidationSeverity
                            .ERROR
                        ),
                        field="require_citations",
                        message=(
                            "Deep research must require "
                            "citations."
                        ),
                    )
                )

            if request.maximum_sources < (
                self.MINIMUM_DEEP_RESEARCH_SOURCES
            ):
                issues.append(
                    self._issue(
                        code=(
                            ResearchRequestValidationCode
                            .DEEP_RESEARCH_REQUIRES_MORE_SOURCES
                        ),
                        severity=(
                            ResearchRequestValidationSeverity
                            .ERROR
                        ),
                        field="maximum_sources",
                        message=(
                            "Deep research must allow at least "
                            f"{self.MINIMUM_DEEP_RESEARCH_SOURCES} "
                            "sources."
                        ),
                    )
                )

        if (
            request.depth is ResearchDepth.QUICK
            and request.maximum_sources
            > self.QUICK_RESEARCH_SOURCE_WARNING_LIMIT
        ):
            issues.append(
                self._issue(
                    code=(
                        ResearchRequestValidationCode
                        .QUICK_RESEARCH_HIGH_SOURCE_LIMIT
                    ),
                    severity=(
                        ResearchRequestValidationSeverity.WARNING
                    ),
                    field="maximum_sources",
                    message=(
                        "Quick research has a high source limit "
                        "that may increase cost and latency."
                    ),
                )
            )

    def _validate_research_scope(
        self,
        *,
        request: ResearchRequest,
        issues: list[ResearchRequestValidationIssue],
    ) -> None:
        """Warn when useful scope preferences are absent."""

        if not request.preferred_source_types:
            issues.append(
                self._issue(
                    code=(
                        ResearchRequestValidationCode
                        .NO_PREFERRED_SOURCE_TYPES
                    ),
                    severity=(
                        ResearchRequestValidationSeverity.WARNING
                    ),
                    field="preferred_source_types",
                    message=(
                        "No preferred source types were supplied."
                    ),
                )
            )

        if not request.include_topics:
            issues.append(
                self._issue(
                    code=(
                        ResearchRequestValidationCode
                        .NO_INCLUDED_TOPICS
                    ),
                    severity=(
                        ResearchRequestValidationSeverity.WARNING
                    ),
                    field="include_topics",
                    message=(
                        "No explicit included research topics "
                        "were supplied."
                    ),
                )
            )

    def _validate_citation_preference(
        self,
        *,
        request: ResearchRequest,
        issues: list[ResearchRequestValidationIssue],
    ) -> None:
        """Warn when non-deep research disables citations."""

        if (
            request.depth is not ResearchDepth.DEEP
            and not request.require_citations
        ):
            issues.append(
                self._issue(
                    code=(
                        ResearchRequestValidationCode
                        .CITATIONS_NOT_REQUIRED
                    ),
                    severity=(
                        ResearchRequestValidationSeverity.WARNING
                    ),
                    field="require_citations",
                    message=(
                        "Research without citations provides "
                        "weaker evidence traceability."
                    ),
                )
            )

    @staticmethod
    def _normalize(value: str) -> str:
        """Return normalized text for semantic equality checks."""

        return " ".join(
            value.strip().casefold().split()
        )

    @staticmethod
    def _issue(
        *,
        code: ResearchRequestValidationCode,
        severity: ResearchRequestValidationSeverity,
        field: str,
        message: str,
    ) -> ResearchRequestValidationIssue:
        """Build one validation issue."""

        return ResearchRequestValidationIssue(
            code=code,
            severity=severity,
            field=field,
            message=message,
        )
