"""Tests for the answer coverage development dataset."""

from collections import Counter

from app.evals.answer_coverage_golden_dataset import (
    build_answer_coverage_golden_dataset,
)
from app.schemas.answer_coverage_judgment import AnswerCoverageLevel


def test_dataset_has_eighteen_cases() -> None:
    dataset = build_answer_coverage_golden_dataset()

    assert len(dataset.cases) == 18
    assert dataset.dataset_id == "answer-coverage-golden-v2"
    assert dataset.version == "2.0.0"


def test_dataset_is_balanced() -> None:
    dataset = build_answer_coverage_golden_dataset()

    counts = Counter(
        case.expected_coverage_level
        for case in dataset.cases
    )

    assert counts == {
        AnswerCoverageLevel.FULLY_COVERED: 6,
        AnswerCoverageLevel.PARTIALLY_COVERED: 6,
        AnswerCoverageLevel.INSUFFICIENT: 6,
    }


def test_case_ids_are_unique() -> None:
    dataset = build_answer_coverage_golden_dataset()

    case_ids = [case.case_id for case in dataset.cases]

    assert len(case_ids) == len(set(case_ids))
