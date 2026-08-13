"""Tests for Phase 10C architecture benchmark interpretation."""

from __future__ import annotations

import pytest

from app.research.hybrid_backend_comparison import summarize_phase10c


def payload() -> dict[str, object]:
    return {
        "aggregate": {
            "pair_count": 2,
            "mean_citation_exact_rate": 1.0,
            "mean_claim_relevance_exact_rate": 0.75,
            "answer_coverage_level_equal_rate": 0.5,
            "mean_answer_coverage_score_delta_local_minus_openai": 0.2,
            "mean_wall_delta_local_minus_openai": {
                "citation": -1.0,
                "relevance": -2.0,
                "coverage": -3.0,
                "total": -6.0,
            },
        },
        "pairs": [
            {
                "openai": {"wall_seconds": {"total": 10.0}},
                "local": {"wall_seconds": {"total": 4.0}},
            },
            {
                "openai": {"wall_seconds": {"total": 14.0}},
                "local": {"wall_seconds": {"total": 6.0}},
            },
        ],
    }


def test_summary_maps_architecture_roles_and_metrics() -> None:
    value = summarize_phase10c(phase7_payload=payload())

    assert value.pair_count == 2
    assert value.local_heavy_distinct is False
    assert value.hybrid_local_roles == (
        "semantic_citation",
        "claim_relevance",
        "answer_coverage",
    )
    assert value.openai_worker_wall_mean_seconds == pytest.approx(12.0)
    assert value.hybrid_local_worker_wall_mean_seconds == pytest.approx(5.0)
    assert value.hybrid_wall_reduction_fraction == pytest.approx(7 / 12)
    assert value.hybrid_speedup_ratio == pytest.approx(2.4)


def test_summary_rejects_missing_pairs() -> None:
    value = payload()
    value["pairs"] = []

    with pytest.raises(
        ValueError,
        match="successful pairs",
    ):
        summarize_phase10c(phase7_payload=value)
