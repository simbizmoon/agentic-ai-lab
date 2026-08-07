"""Tests for the fixed claim relevance golden DEV dataset."""

from __future__ import annotations

from collections import Counter

from app.evals.claim_relevance_golden_dataset import (
    build_claim_relevance_golden_dataset,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)


def test_golden_dataset_has_fixed_identity() -> None:
    dataset = build_claim_relevance_golden_dataset()
    assert dataset.dataset_id == "claim-relevance-golden-v1"
    assert dataset.version == "1.0.0"


def test_golden_dataset_has_eighteen_cases() -> None:
    dataset = build_claim_relevance_golden_dataset()
    assert len(dataset.cases) == 18


def test_golden_dataset_is_balanced() -> None:
    dataset = build_claim_relevance_golden_dataset()
    counts = Counter(
        case.expected_relevance_level
        for case in dataset.cases
    )

    assert counts == {
        ClaimRelevanceLevel.DIRECTLY_RELEVANT: 6,
        ClaimRelevanceLevel.PARTIALLY_RELEVANT: 6,
        ClaimRelevanceLevel.IRRELEVANT: 6,
    }


def test_golden_dataset_case_ids_are_unique() -> None:
    dataset = build_claim_relevance_golden_dataset()
    case_ids = [
        case.case_id.casefold()
        for case in dataset.cases
    ]
    assert len(case_ids) == len(set(case_ids))


def test_golden_dataset_contains_boundary_cases() -> None:
    dataset = build_claim_relevance_golden_dataset()
    case_ids = {case.case_id for case in dataset.cases}

    assert "direct-006-narrow-but-core" in case_ids
    assert "partial-001-use-case-example" in case_ids
    assert "partial-005-mitigation-not-cause" in case_ids
    assert "irrelevant-001-product-positioning" in case_ids
