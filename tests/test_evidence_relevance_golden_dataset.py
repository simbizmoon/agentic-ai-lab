"""Tests for evidence relevance Golden DEV v1 dataset."""

from collections import Counter

from app.evals.evidence_relevance_golden_dataset import (
    evidence_relevance_golden_dev_v1,
)
from app.schemas.evidence_relevance_judgment import (
    EvidenceRelevanceLevel,
)


def test_dataset_is_balanced_and_fixed() -> None:
    dataset = evidence_relevance_golden_dev_v1()

    assert dataset.dataset_id == "evidence-relevance-golden-dev-v1"
    assert len(dataset.cases) == 18

    counts = Counter(
        case.expected_level
        for case in dataset.cases
    )

    assert counts == {
        EvidenceRelevanceLevel.DIRECTLY_RELEVANT: 6,
        EvidenceRelevanceLevel.PARTIALLY_RELEVANT: 6,
        EvidenceRelevanceLevel.IRRELEVANT: 6,
    }


def test_case_ids_are_unique() -> None:
    dataset = evidence_relevance_golden_dev_v1()
    case_ids = [case.case_id for case in dataset.cases]

    assert len(case_ids) == len(set(case_ids))
