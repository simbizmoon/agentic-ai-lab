"""Tests for semantic answer coverage judgment schema."""

import pytest
from pydantic import ValidationError

from app.schemas.answer_coverage_judgment import (
    AnswerCoverageJudgment,
    AnswerCoverageLevel,
)


def test_fully_covered_accepts_no_missing_aspects() -> None:
    value = AnswerCoverageJudgment(
        coverage_level=AnswerCoverageLevel.FULLY_COVERED,
        coverage_score=0.95,
        covered_aspects=["exposure", "execution"],
        missing_aspects=[],
        rationale="All requested mechanism parts are represented.",
    )

    assert value.coverage_level is AnswerCoverageLevel.FULLY_COVERED


def test_fully_covered_rejects_missing_aspects() -> None:
    with pytest.raises(
        ValidationError,
        match="fully_covered must not include missing_aspects",
    ):
        AnswerCoverageJudgment(
            coverage_level=AnswerCoverageLevel.FULLY_COVERED,
            coverage_score=0.9,
            covered_aspects=["exposure"],
            missing_aspects=["execution"],
            rationale="Incomplete.",
        )


def test_rejects_duplicate_aspects_case_insensitively() -> None:
    with pytest.raises(
        ValidationError,
        match="covered_aspects must not contain duplicates",
    ):
        AnswerCoverageJudgment(
            coverage_level=AnswerCoverageLevel.PARTIALLY_COVERED,
            coverage_score=0.6,
            covered_aspects=["Execution", "execution"],
            missing_aspects=["result handling"],
            rationale="Partial coverage.",
        )
