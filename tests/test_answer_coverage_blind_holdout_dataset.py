"""Tests for the fresh answer coverage blind holdout dataset."""

from collections import Counter

from app.evals.answer_coverage_blind_holdout_dataset import (
    build_answer_coverage_blind_holdout_dataset,
)
from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


def test_blind_holdout_has_twenty_cases() -> None:
    dataset = build_answer_coverage_blind_holdout_dataset()

    assert len(dataset.cases) == 20
    assert dataset.dataset_id == "answer-coverage-blind-holdout-v1"
    assert dataset.version == "1.0.0"


def test_blind_holdout_distribution() -> None:
    dataset = build_answer_coverage_blind_holdout_dataset()

    counts = Counter(
        case.expected_coverage_level
        for case in dataset.cases
    )

    assert counts == {
        AnswerCoverageLevel.FULLY_COVERED: 7,
        AnswerCoverageLevel.PARTIALLY_COVERED: 7,
        AnswerCoverageLevel.INSUFFICIENT: 6,
    }


def test_blind_holdout_case_ids_are_unique() -> None:
    dataset = build_answer_coverage_blind_holdout_dataset()

    case_ids = [case.case_id for case in dataset.cases]

    assert len(case_ids) == len(set(case_ids))
