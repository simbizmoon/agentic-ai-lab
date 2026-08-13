"""Deterministic approved quality review for architecture benchmarks."""

from __future__ import annotations

from app.research.research_quality_review_executor import (
    ResearchQualityDecision,
    ResearchQualityReview,
    ResearchQualityReviewExecutionResult,
    ResearchQualityReviewExecutor,
    ResearchQualityScores,
)
from app.schemas.research_agent_assignment import ResearchAgentTaskAssignment


class DeterministicApprovedQualityReviewExecutor(
    ResearchQualityReviewExecutor
):
    """Approve a known synthesized report without external model calls."""

    def __init__(self, *, report_id: str) -> None:
        cleaned = report_id.strip()
        if not cleaned:
            raise ValueError("report_id must not be blank")
        self._report_id = cleaned

    def execute(
        self,
        assignment: ResearchAgentTaskAssignment,
    ) -> ResearchQualityReviewExecutionResult:
        """Return one zero-cost deterministic approval."""

        review = ResearchQualityReview(
            review_id=f"{self._report_id}-deterministic-review",
            report_id=self._report_id,
            decision=ResearchQualityDecision.APPROVED,
            scores=ResearchQualityScores(
                completeness=1.0,
                evidence_coverage=1.0,
                citation_quality=1.0,
                source_quality=1.0,
                logical_consistency=1.0,
                clarity=1.0,
            ),
            summary=(
                "Deterministic architecture benchmark approval. "
                "This result measures workflow overhead and is not "
                "an independent semantic quality judgment."
            ),
            strengths=[
                "The benchmark review completed without an external model call."
            ],
            metadata={
                "provider": "deterministic-benchmark",
                "authoritative": "false",
                "purpose": "architecture-overhead-isolation",
                "assignment_id": assignment.assignment_id,
            },
        )
        return ResearchQualityReviewExecutionResult(
            review=review,
            tool_call_count=0,
            duration_ms=0,
            input_token_count=0,
            output_token_count=0,
            metadata={
                "provider": "deterministic-benchmark",
                "authoritative": "false",
            },
        )
