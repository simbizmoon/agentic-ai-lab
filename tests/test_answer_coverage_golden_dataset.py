"""Tests for the answer coverage development dataset."""

from app.evals.answer_coverage_golden_dataset import (
    build_answer_coverage_golden_dataset,
)
from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


def test_dataset_is_balanced() -> None:
    dataset = build_answer_coverage_golden_dataset()

    counts = {
        level: sum(
            case.expected_coverage_level is level
            for case in dataset.cases
        )
        for level in AnswerCoverageLevel
    }

    assert counts == {
        AnswerCoverageLevel.FULLY_COVERED: 2,
        AnswerCoverageLevel.PARTIALLY_COVERED: 2,
        AnswerCoverageLevel.INSUFFICIENT: 2,
    }
