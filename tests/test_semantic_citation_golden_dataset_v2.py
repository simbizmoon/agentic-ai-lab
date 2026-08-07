"""Tests for semantic citation golden dataset v2."""

from __future__ import annotations

from collections import Counter

from app.evals.semantic_citation_golden_dataset_v2 import (
    build_semantic_citation_golden_dataset_v2,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


def test_v2_dataset_has_fixed_identity() -> None:
    dataset = build_semantic_citation_golden_dataset_v2()

    assert dataset.dataset_id == "semantic-citation-golden-v2"
    assert dataset.version == "2.0.0"


def test_v2_dataset_has_twenty_cases() -> None:
    dataset = build_semantic_citation_golden_dataset_v2()

    assert len(dataset.cases) == 20


def test_v2_dataset_support_level_distribution() -> None:
    dataset = build_semantic_citation_golden_dataset_v2()

    counts = Counter(
        case.expected_support_level
        for case in dataset.cases
    )

    assert counts == {
        SemanticCitationSupportLevel.FULLY_SUPPORTED: 4,
        SemanticCitationSupportLevel.PARTIALLY_SUPPORTED: 5,
        SemanticCitationSupportLevel.UNSUPPORTED: 5,
        SemanticCitationSupportLevel.CONTRADICTED: 6,
    }


def test_v2_preserves_v1_dataset_separately() -> None:
    dataset = build_semantic_citation_golden_dataset_v2()

    assert dataset.dataset_id != "semantic-citation-golden-v1"
