"""Tests for frozen bounded-worker backend comparison."""


from pathlib import Path

import pytest

from app.research.frozen_worker_backend_comparison import (
    compare_frozen_pair,
    load_frozen_input,
)
from app.schemas.research_request import (
    ResearchDepth,
    ResearchOutputFormat,
)


def run(
    *,
    provider: str,
    citation_level: str = "fully_supported",
    relevance_level: str = "directly_relevant",
    coverage_level: str = "fully_covered",
    coverage_score: float = 1.0,
    wall: float = 1.0,
) -> dict:
    decision = (
        "verified"
        if citation_level == "fully_supported"
        else "needs_revision"
    )
    return {
        "provider": provider,
        "fixture_path": "fixture.json",
        "citation_verifications": [
            {
                "claim_id": "claim-1",
                "citation_id": "citation-1",
                "decision": decision,
                "support_level": citation_level,
            }
        ],
        "claim_relevance_evaluations": [
            {
                "claim_id": "claim-1",
                "relevance_level": relevance_level,
            }
        ],
        "answer_coverage_evaluation": {
            "claim_ids": ["claim-1"],
            "coverage_level": coverage_level,
            "coverage_score": coverage_score,
        },
        "wall_seconds": {
            "citation": wall,
            "claim_relevance": wall,
            "answer_coverage": wall,
            "total": wall * 3,
        },
    }


def test_compare_frozen_pair_reports_exact_agreement() -> None:
    comparison = compare_frozen_pair(
        openai_run=run(provider="openai", wall=2.0),
        local_run=run(provider="local", wall=1.0),
    )

    assert comparison["agreement"]["citation_exact_rate"] == 1.0
    assert comparison["agreement"]["claim_relevance_exact_rate"] == 1.0
    assert comparison["agreement"]["answer_coverage_level_equal"] is True
    assert comparison["wall_delta_local_minus_openai"]["total"] == (
        pytest.approx(-3.0)
    )


def test_compare_frozen_pair_reports_disagreement() -> None:
    comparison = compare_frozen_pair(
        openai_run=run(provider="openai"),
        local_run=run(
            provider="local",
            citation_level="partially_supported",
            relevance_level="partially_relevant",
            coverage_level="partially_covered",
            coverage_score=0.6,
        ),
    )

    assert comparison["agreement"]["citation_exact_rate"] == 0.0
    assert comparison["agreement"]["claim_relevance_exact_rate"] == 0.0
    assert comparison["agreement"]["answer_coverage_level_equal"] is False
    assert comparison["agreement"][
        "answer_coverage_score_delta_local_minus_openai"
    ] == pytest.approx(-0.4)

def test_load_frozen_input_accepts_persisted_json_enums(
    tmp_path: Path,
) -> None:
    source = Path(
        "/mnt/ai-data/experiments/phase7/"
        "20260813T025158Z_openai-vs-local/"
        "pair-01/openai/"
        "aira-live-4b638fb57405434587437a1d82cbcee5/"
        "result.json"
    )

    if not source.exists():
        pytest.skip("Phase 7 persisted fixture is not available")

    fixture = tmp_path / "result.json"
    fixture.write_text(
        source.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    frozen = load_frozen_input(fixture)

    assert frozen.request.depth is ResearchDepth.QUICK
    assert (
        frozen.request.output_format
        is ResearchOutputFormat.BRIEF
    )
    assert (
        frozen.claim_set.request_id
        == frozen.request.request_id
    )

