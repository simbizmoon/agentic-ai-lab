"""Tests for recorded answer coverage evaluation schema."""

import pytest
from pydantic import ValidationError

from app.schemas.answer_coverage_judgment import AnswerCoverageLevel
from app.schemas.research_answer_coverage_evaluation import (
    ResearchAnswerCoverageEvaluation,
)


def test_accepts_valid_evaluation() -> None:
    value = ResearchAnswerCoverageEvaluation(
        evaluation_id="answer-coverage-001",
        request_id="research-001",
        claim_ids=["claim-001", "claim-002"],
        coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
        coverage_score=0.65,
        covered_aspects=["tool exposure"],
        missing_aspects=["runtime execution"],
        rationale="The claim set covers exposure but not execution.",
        metadata={"model": "test-model"},
    )

    assert value.claim_ids == ["claim-001", "claim-002"]


def test_rejects_duplicate_claim_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="claim_ids must not contain duplicates",
    ):
        ResearchAnswerCoverageEvaluation(
            evaluation_id="answer-coverage-001",
            request_id="research-001",
            claim_ids=["claim-001", "CLAIM-001"],
            coverage_level=AnswerCoverageLevel.INSUFFICIENT,
            coverage_score=0.2,
            rationale="Insufficient.",
        )
