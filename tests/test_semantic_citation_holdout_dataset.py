"""Tests for the blind semantic citation holdout dataset."""

from __future__ import annotations

from collections import Counter

from app.evals.semantic_citation_holdout_dataset import (
    build_semantic_citation_holdout_dataset,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


def test_holdout_has_fixed_identity() -> None:
    dataset = build_semantic_citation_holdout_dataset()

    assert dataset.dataset_id == "semantic-citation-holdout-v1"
    assert dataset.version == "1.0.0"


def test_holdout_has_twenty_cases() -> None:
    dataset = build_semantic_citation_holdout_dataset()

    assert len(dataset.cases) == 20


def test_holdout_is_balanced() -> None:
    dataset = build_semantic_citation_holdout_dataset()

    counts = Counter(
        case.expected_support_level
        for case in dataset.cases
    )

    assert counts == {
        SemanticCitationSupportLevel.FULLY_SUPPORTED: 5,
        SemanticCitationSupportLevel.PARTIALLY_SUPPORTED: 5,
        SemanticCitationSupportLevel.UNSUPPORTED: 5,
        SemanticCitationSupportLevel.CONTRADICTED: 5,
    }


def test_holdout_case_ids_are_unique() -> None:
    dataset = build_semantic_citation_holdout_dataset()

    case_ids = [
        case.case_id
        for case in dataset.cases
    ]

    assert len(case_ids) == len(set(case_ids))


def test_holdout_does_not_reuse_golden_dataset_identity() -> None:
    dataset = build_semantic_citation_holdout_dataset()

    assert dataset.dataset_id not in {
        "semantic-citation-golden-v1",
        "semantic-citation-golden-v2",
    }
