"""Tests for final research quality schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.research_quality import (
    ResearchQualityEvaluation,
    ResearchQualityIssue,
    ResearchQualityIssueCode,
    ResearchQualityIssueSeverity,
    ResearchQualityLevel,
)
from app.schemas.research_synthesis import (
    ResearchSynthesisCitation,
    ResearchSynthesisReport,
    ResearchSynthesisSection,
)


def report() -> ResearchSynthesisReport:
    """Return one valid synthesized report."""

    citation = ResearchSynthesisCitation(
        citation_id="citation-001",
        evidence_id="evidence-001",
        source_id="source-001",
        document_id="document-001",
        label="[1]",
        title="Research source",
        url="https://example.com/source",
        excerpt="Supported finding.",
    )

    section = ResearchSynthesisSection(
        section_id="section-001",
        task_id="task-001",
        title="Findings",
        content="1. Supported finding. [1]",
        order=1,
        claim_ids=["claim-001"],
        citation_ids=["citation-001"],
    )

    return ResearchSynthesisReport(
        report_id="research-001-report",
        workspace_id="workspace-001",
        request_id="research-001",
        title="Research Report",
        executive_summary="Research summary.",
        sections=[section],
        citations=[citation],
        claim_count=1,
        citation_count=1,
        source_count=1,
        synthesizer="test-synthesizer",
    )


def evaluation(
    **overrides: object,
) -> ResearchQualityEvaluation:
    """Return one valid research quality evaluation."""

    values: dict[str, object] = {
        "report": report(),
        "evaluator": "test-evaluator",
        "claim_coverage_score": 1.0,
        "citation_coverage_score": 1.0,
        "source_diversity_score": 1.0,
        "source_quality_score": 0.8,
        "contradiction_handling_score": 1.0,
        "overall_score": 0.96,
        "quality_level": ResearchQualityLevel.EXCELLENT,
        "issues": [],
        "metadata": {
            "method": "test",
        },
    }
    values.update(overrides)

    return ResearchQualityEvaluation.model_validate(
        values
    )


def test_evaluation_accepts_valid_values() -> None:
    value = evaluation()

    assert value.quality_level is (
        ResearchQualityLevel.EXCELLENT
    )
    assert value.passed is True


def test_evaluation_rejects_blank_evaluator() -> None:
    with pytest.raises(
        ValidationError,
        match="evaluator must not be blank",
    ):
        evaluation(evaluator=" ")


def test_evaluation_rejects_wrong_level() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "quality_level must match overall_score"
        ),
    ):
        evaluation(
            overall_score=0.4,
            quality_level=ResearchQualityLevel.HIGH,
        )


def test_evaluation_reports_failed_on_error() -> None:
    value = evaluation(
        issues=[
            ResearchQualityIssue(
                code=(
                    ResearchQualityIssueCode.MISSING_CLAIMS
                ),
                severity=(
                    ResearchQualityIssueSeverity.ERROR
                ),
                message="A claim is missing.",
                related_ids=["claim-001"],
            )
        ]
    )

    assert value.passed is False


def test_issue_rejects_blank_message() -> None:
    with pytest.raises(
        ValidationError,
        match="message must not be blank",
    ):
        ResearchQualityIssue(
            code=ResearchQualityIssueCode.MISSING_CLAIMS,
            severity=ResearchQualityIssueSeverity.ERROR,
            message=" ",
        )


def test_issue_rejects_duplicate_related_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "related_ids must not contain duplicates"
        ),
    ):
        ResearchQualityIssue(
            code=ResearchQualityIssueCode.MISSING_CLAIMS,
            severity=ResearchQualityIssueSeverity.ERROR,
            message="Claims are missing.",
            related_ids=[
                "claim-001",
                " CLAIM-001 ",
            ],
        )


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.95, ResearchQualityLevel.EXCELLENT),
        (0.90, ResearchQualityLevel.EXCELLENT),
        (0.89, ResearchQualityLevel.HIGH),
        (0.75, ResearchQualityLevel.HIGH),
        (0.74, ResearchQualityLevel.MEDIUM),
        (0.50, ResearchQualityLevel.MEDIUM),
        (0.49, ResearchQualityLevel.LOW),
    ],
)
def test_level_for_score(
    score: float,
    expected: ResearchQualityLevel,
) -> None:
    assert (
        ResearchQualityEvaluation.level_for_score(
            score
        )
        is expected
    )
