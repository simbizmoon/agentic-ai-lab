"""Tests for the fresh v2 claim relevance DEV dataset."""

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
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)


def test_v2_dataset_has_fixed_identity() -> None:
    dataset = build_claim_relevance_golden_dataset_v2()
    assert dataset.dataset_id == "claim-relevance-golden-v2"
    assert dataset.version == "2.0.0"


def test_v2_dataset_has_eighteen_cases() -> None:
    dataset = build_claim_relevance_golden_dataset_v2()
    assert len(dataset.cases) == 18


def test_v2_dataset_is_balanced() -> None:
    dataset = build_claim_relevance_golden_dataset_v2()
    counts = Counter(
        case.expected_relevance_level
        for case in dataset.cases
    )

    assert counts == {
        ClaimRelevanceLevel.DIRECTLY_RELEVANT: 6,
        ClaimRelevanceLevel.PARTIALLY_RELEVANT: 6,
        ClaimRelevanceLevel.IRRELEVANT: 6,
    }


def test_v2_case_ids_are_unique() -> None:
    dataset = build_claim_relevance_golden_dataset_v2()
    ids = [case.case_id.casefold() for case in dataset.cases]
    assert len(ids) == len(set(ids))


def test_v2_identity_differs_from_prior_datasets() -> None:
    v2 = build_claim_relevance_golden_dataset_v2()
    v1 = build_claim_relevance_golden_dataset()
    holdout = build_claim_relevance_holdout_dataset()

    assert v2.dataset_id not in {
        v1.dataset_id,
        holdout.dataset_id,
    }


def test_v2_does_not_reuse_prior_case_ids() -> None:
    v2 = build_claim_relevance_golden_dataset_v2()
    prior = [
        *build_claim_relevance_golden_dataset().cases,
        *build_claim_relevance_holdout_dataset().cases,
    ]

    v2_ids = {case.case_id.casefold() for case in v2.cases}
    prior_ids = {case.case_id.casefold() for case in prior}

    assert v2_ids.isdisjoint(prior_ids)


def test_v2_contains_policy_boundary_cases() -> None:
    dataset = build_claim_relevance_golden_dataset_v2()
    ids = {case.case_id for case in dataset.cases}

    assert "v2-partial-002-auth-prerequisite" in ids
    assert "v2-partial-003-commonality" in ids
    assert "v2-partial-006-state-link" in ids
    assert "v2-irrelevant-002-posthoc-audit" in ids
    assert "v2-irrelevant-004-versioning" in ids
