"""Offline tests for the human-review-only Stage 9 candidate catalog."""

from app.evals.stage9_golden_candidate_catalog import (
    build_stage9_golden_candidate_catalog,
)
from app.schemas.stage9_evaluation_manifest import Stage9EvaluationDomain


def test_catalog_has_exactly_ten_unique_candidates_and_all_domains() -> None:
    catalog = build_stage9_golden_candidate_catalog()
    assert len(catalog.candidates) == 10
    assert len({item.candidate_id for item in catalog.candidates}) == 10
    assert {item.domain for item in catalog.candidates} == set(Stage9EvaluationDomain)


def test_candidates_are_not_locked_and_have_review_boundaries() -> None:
    for candidate in build_stage9_golden_candidate_catalog().candidates:
        assert candidate.locked is False
        assert candidate.source_ids
        assert candidate.prohibited_claims
        assert candidate.expected_uncertainties


def test_catalog_mix_is_two_technical_two_academic_three_patent_three_cross() -> None:
    counts = {domain: 0 for domain in Stage9EvaluationDomain}
    for candidate in build_stage9_golden_candidate_catalog().candidates:
        counts[candidate.domain] += 1
    assert tuple(counts.values()) == (2, 2, 3, 3)
