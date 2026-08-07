"""Tests for the semantic citation golden dataset."""

from __future__ import annotations

from collections import Counter

from app.evals.semantic_citation_golden_dataset import (
    build_semantic_citation_golden_dataset,
)
from app.schemas.semantic_citation_judgment import (
    SemanticCitationSupportLevel,
)


def test_dataset_has_fixed_identity() -> None:
    dataset = build_semantic_citation_golden_dataset()

    assert dataset.dataset_id == (
        "semantic-citation-golden-v1"
    )
    assert dataset.version == "1.0.0"


def test_dataset_has_sixteen_cases() -> None:
    dataset = build_semantic_citation_golden_dataset()

    assert len(dataset.cases) == 16


def test_dataset_is_balanced_across_support_levels() -> None:
    dataset = build_semantic_citation_golden_dataset()

    counts = Counter(
        case.expected_support_level
        for case in dataset.cases
    )

    assert counts == {
        SemanticCitationSupportLevel.FULLY_SUPPORTED: 4,
        SemanticCitationSupportLevel.PARTIALLY_SUPPORTED: 4,
        SemanticCitationSupportLevel.UNSUPPORTED: 4,
        SemanticCitationSupportLevel.CONTRADICTED: 4,
    }


def test_dataset_case_ids_are_stable() -> None:
    dataset = build_semantic_citation_golden_dataset()

    assert [
        case.case_id
        for case in dataset.cases
    ] == [
        "fully-001-verbatim",
        "fully-002-paraphrase",
        "fully-003-narrower",
        "fully-004-number-preserved",
        "partial-001-conjunction",
        "partial-002-qualifier",
        "partial-003-number",
        "partial-004-condition",
        "unsupported-001-unrelated",
        "unsupported-002-entity",
        "unsupported-003-causal-leap",
        "unsupported-004-capability",
        "contradicted-001-required",
        "contradicted-002-none",
        "contradicted-003-direction",
        "contradicted-004-temporal",
    ]
