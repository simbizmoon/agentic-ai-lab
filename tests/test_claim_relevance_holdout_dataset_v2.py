"""Tests for the fresh blind claim relevance holdout v2 dataset."""

from __future__ import annotations

from collections import Counter

from app.evals.claim_relevance_golden_dataset import (
    build_claim_relevance_golden_dataset,
)
from app.evals.claim_relevance_golden_dataset_v2 import (
    build_claim_relevance_golden_dataset_v2,
)
from app.evals.claim_relevance_holdout_dataset import (
    build_claim_relevance_holdout_dataset,
)
from app.evals.claim_relevance_holdout_dataset_v2 import (
    build_claim_relevance_holdout_dataset_v2,
)
from app.schemas.claim_relevance_judgment import ClaimRelevanceLevel


def test_holdout_v2_has_fixed_identity() -> None:
    dataset = build_claim_relevance_holdout_dataset_v2()

    assert dataset.dataset_id == "claim-relevance-holdout-v2"
    assert dataset.version == "2.0.0"


def test_holdout_v2_has_eighteen_cases() -> None:
    dataset = build_claim_relevance_holdout_dataset_v2()

    assert len(dataset.cases) == 18


def test_holdout_v2_is_balanced() -> None:
    dataset = build_claim_relevance_holdout_dataset_v2()
    counts = Counter(
        case.expected_relevance_level
        for case in dataset.cases
    )

    assert counts == {
        ClaimRelevanceLevel.DIRECTLY_RELEVANT: 6,
        ClaimRelevanceLevel.PARTIALLY_RELEVANT: 6,
        ClaimRelevanceLevel.IRRELEVANT: 6,
    }


def test_holdout_v2_case_ids_are_unique() -> None:
    dataset = build_claim_relevance_holdout_dataset_v2()
    ids = [case.case_id.casefold() for case in dataset.cases]

    assert len(ids) == len(set(ids))


def test_holdout_v2_identity_is_new() -> None:
    current = build_claim_relevance_holdout_dataset_v2()
    prior = {
        build_claim_relevance_golden_dataset().dataset_id,
        build_claim_relevance_holdout_dataset().dataset_id,
        build_claim_relevance_golden_dataset_v2().dataset_id,
    }

    assert current.dataset_id not in prior


def test_holdout_v2_case_ids_do_not_reuse_prior_ids() -> None:
    current = build_claim_relevance_holdout_dataset_v2()
    prior_cases = [
        *build_claim_relevance_golden_dataset().cases,
        *build_claim_relevance_holdout_dataset().cases,
        *build_claim_relevance_golden_dataset_v2().cases,
    ]

    current_ids = {case.case_id.casefold() for case in current.cases}
    prior_ids = {case.case_id.casefold() for case in prior_cases}

    assert current_ids.isdisjoint(prior_ids)


def test_holdout_v2_contains_new_boundary_themes() -> None:
    dataset = build_claim_relevance_holdout_dataset_v2()
    ids = {case.case_id for case in dataset.cases}

    assert "holdout-v2-partial-001-secret-inventory" in ids
    assert "holdout-v2-partial-004-latency-measurement" in ids
    assert "holdout-v2-partial-005-capability-catalog" in ids
    assert "holdout-v2-irrelevant-003-approval-notification-theme" in ids
