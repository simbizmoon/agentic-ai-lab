"""Tests for the blind claim relevance holdout dataset."""

from __future__ import annotations

from collections import Counter

from app.evals.claim_relevance_golden_dataset import (
    build_claim_relevance_golden_dataset,
)
from app.evals.claim_relevance_holdout_dataset import (
    build_claim_relevance_holdout_dataset,
)
from app.schemas.claim_relevance_judgment import (
    ClaimRelevanceLevel,
)


def test_holdout_has_fixed_identity() -> None:
    dataset = build_claim_relevance_holdout_dataset()
    assert dataset.dataset_id == "claim-relevance-holdout-v1"
    assert dataset.version == "1.0.0"


def test_holdout_has_eighteen_cases() -> None:
    dataset = build_claim_relevance_holdout_dataset()
    assert len(dataset.cases) == 18


def test_holdout_is_balanced() -> None:
    dataset = build_claim_relevance_holdout_dataset()
    counts = Counter(
        case.expected_relevance_level
        for case in dataset.cases
    )

    assert counts == {
        ClaimRelevanceLevel.DIRECTLY_RELEVANT: 6,
        ClaimRelevanceLevel.PARTIALLY_RELEVANT: 6,
        ClaimRelevanceLevel.IRRELEVANT: 6,
    }


def test_holdout_case_ids_are_unique() -> None:
    dataset = build_claim_relevance_holdout_dataset()
    ids = [case.case_id.casefold() for case in dataset.cases]
    assert len(ids) == len(set(ids))


def test_holdout_identity_differs_from_golden() -> None:
    holdout = build_claim_relevance_holdout_dataset()
    golden = build_claim_relevance_golden_dataset()

    assert holdout.dataset_id != golden.dataset_id


def test_holdout_does_not_reuse_golden_case_ids() -> None:
    holdout = build_claim_relevance_holdout_dataset()
    golden = build_claim_relevance_golden_dataset()

    holdout_ids = {case.case_id.casefold() for case in holdout.cases}
    golden_ids = {case.case_id.casefold() for case in golden.cases}

    assert holdout_ids.isdisjoint(golden_ids)


def test_holdout_contains_boundary_cases() -> None:
    dataset = build_claim_relevance_holdout_dataset()
    ids = {case.case_id for case in dataset.cases}

    assert "holdout-partial-002-audit-not-auth" in ids
    assert "holdout-partial-004-monitoring-not-eval" in ids
    assert "holdout-partial-005-source-list-not-provenance" in ids
    assert "holdout-irrelevant-002-tool-description" in ids
