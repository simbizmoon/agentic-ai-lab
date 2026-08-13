"""Tests for deterministic benchmark quality review."""

from __future__ import annotations

from types import SimpleNamespace

from app.research.deterministic_quality_review_executor import (
    DeterministicApprovedQualityReviewExecutor,
)
from app.research.research_quality_review_executor import (
    ResearchQualityDecision,
)


def test_deterministic_review_approves_without_model_cost() -> None:
    executor = DeterministicApprovedQualityReviewExecutor(
        report_id="report-001"
    )

    result = executor.execute(
        SimpleNamespace(assignment_id="assignment-001")  # type: ignore[arg-type]
    )

    assert result.review is not None
    assert result.review.report_id == "report-001"
    assert result.review.decision is ResearchQualityDecision.APPROVED
    assert result.tool_call_count == 0
    assert result.input_token_count == 0
    assert result.output_token_count == 0
    assert result.metadata["provider"] == "deterministic-benchmark"
