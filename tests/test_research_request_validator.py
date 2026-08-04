"""Tests for deterministic research request readiness validation."""

from app.research.research_request_validator import (
    ResearchRequestValidator,
)
from app.schemas.research_request import (
    ResearchDepth,
    ResearchRequest,
    ResearchSourceType,
)
from app.schemas.research_request_validation import (
    ResearchRequestValidationCode,
    ResearchRequestValidationSeverity,
)


def request(
    **overrides: object,
) -> ResearchRequest:
    """Return one operationally ready research request."""

    values: dict[str, object] = {
        "request_id": "research-001",
        "question": (
            "How do agent memory architectures differ?"
        ),
        "objective": (
            "Compare major memory patterns and explain "
            "their engineering trade-offs."
        ),
        "depth": ResearchDepth.STANDARD,
        "include_topics": [
            "working memory",
            "episodic memory",
        ],
        "preferred_source_types": [
            ResearchSourceType.PRIMARY_RESEARCH,
        ],
        "maximum_sources": 10,
        "require_citations": True,
    }
    values.update(overrides)

    return ResearchRequest.model_validate(values)


def issue_codes(
    result: object,
) -> set[ResearchRequestValidationCode]:
    """Return issue codes from a validation result."""

    return {
        issue.code
        for issue in result.issues
    }


def test_validator_accepts_ready_request() -> None:
    result = ResearchRequestValidator().validate(
        request()
    )

    assert result.valid is True
    assert result.error_count == 0
    assert result.warning_count == 0
    assert result.issues == []


def test_validator_rejects_short_question() -> None:
    result = ResearchRequestValidator().validate(
        request(question="Too short")
    )

    assert result.valid is False
    assert (
        ResearchRequestValidationCode.QUESTION_TOO_SHORT
        in issue_codes(result)
    )


def test_validator_rejects_short_objective() -> None:
    result = ResearchRequestValidator().validate(
        request(objective="Too short")
    )

    assert result.valid is False
    assert (
        ResearchRequestValidationCode.OBJECTIVE_TOO_SHORT
        in issue_codes(result)
    )


def test_validator_rejects_duplicate_question_and_objective() -> None:
    same_text = (
        "Compare major agent memory architecture patterns."
    )

    result = ResearchRequestValidator().validate(
        request(
            question=same_text,
            objective=(
                "  compare   major agent memory "
                "architecture patterns. "
            ),
        )
    )

    assert result.valid is False
    assert (
        ResearchRequestValidationCode
        .QUESTION_OBJECTIVE_DUPLICATE
        in issue_codes(result)
    )


def test_deep_research_requires_citations() -> None:
    result = ResearchRequestValidator().validate(
        request(
            depth=ResearchDepth.DEEP,
            require_citations=False,
        )
    )

    assert result.valid is False
    assert (
        ResearchRequestValidationCode
        .DEEP_RESEARCH_REQUIRES_CITATIONS
        in issue_codes(result)
    )


def test_deep_research_requires_source_capacity() -> None:
    result = ResearchRequestValidator().validate(
        request(
            depth=ResearchDepth.DEEP,
            maximum_sources=4,
        )
    )

    assert result.valid is False
    assert (
        ResearchRequestValidationCode
        .DEEP_RESEARCH_REQUIRES_MORE_SOURCES
        in issue_codes(result)
    )


def test_missing_scope_preferences_produce_warnings() -> None:
    result = ResearchRequestValidator().validate(
        request(
            include_topics=[],
            preferred_source_types=[],
        )
    )

    assert result.valid is True
    assert result.error_count == 0
    assert result.warning_count == 2
    assert (
        ResearchRequestValidationCode
        .NO_INCLUDED_TOPICS
        in issue_codes(result)
    )
    assert (
        ResearchRequestValidationCode
        .NO_PREFERRED_SOURCE_TYPES
        in issue_codes(result)
    )


def test_quick_research_high_source_limit_warns() -> None:
    result = ResearchRequestValidator().validate(
        request(
            depth=ResearchDepth.QUICK,
            maximum_sources=30,
        )
    )

    assert result.valid is True
    assert (
        ResearchRequestValidationCode
        .QUICK_RESEARCH_HIGH_SOURCE_LIMIT
        in issue_codes(result)
    )


def test_standard_research_without_citations_warns() -> None:
    result = ResearchRequestValidator().validate(
        request(require_citations=False)
    )

    assert result.valid is True
    assert (
        ResearchRequestValidationCode
        .CITATIONS_NOT_REQUIRED
        in issue_codes(result)
    )


def test_deep_research_can_return_multiple_errors() -> None:
    result = ResearchRequestValidator().validate(
        request(
            depth=ResearchDepth.DEEP,
            maximum_sources=2,
            require_citations=False,
        )
    )

    assert result.valid is False
    assert result.error_count == 2

    assert all(
        issue.severity
        is ResearchRequestValidationSeverity.ERROR
        for issue in result.issues
    )
