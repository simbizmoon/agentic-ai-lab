"""Tests for Phase 7 single-agent worker-backend comparison."""

import json
from pathlib import Path

import pytest

from app.research.single_agent_backend_comparison import (
    aggregate_pairs,
    compare_pair,
    summarize_result,
)


def write_result(
    path: Path,
    *,
    quality_score: float,
    response_id: str,
    worker_elapsed: float,
) -> None:
    data = {
        "workspace": {
            "document_set": {"documents": [{"document_id": "d1"}]},
            "evidence_set": {"evidence": [{"evidence_id": "e1"}]},
            "claim_set": {
                "claims": [
                    {
                        "claim_id": "c1",
                        "citations": [{"citation_id": "cit1"}],
                    }
                ]
            },
        },
        "quality": {
            "overall_score": quality_score,
            "quality_level": "high",
            "passed": True,
        },
        "citation_verifications": [
            {
                "decision": "verified",
                "support_level": "fully_supported",
                "metadata": {"response_id": response_id},
            }
        ],
        "claim_relevance_evaluations": [
            {
                "relevance_level": "directly_relevant",
                "metadata": {"response_id": response_id},
            }
        ],
        "answer_coverage_evaluation": {
            "coverage_level": "fully_covered",
            "coverage_score": 0.95,
            "metadata": {"response_id": response_id},
        },
        "run_metrics": {
            "total_elapsed_seconds": 10.0,
            "round_1_claim_generation": {
                "call_count": 1,
                "recorded_tokens": 100,
                "elapsed_seconds": 2.0,
            },
            "round_1_citation_verification": {
                "call_count": 1,
                "recorded_tokens": 20,
                "elapsed_seconds": worker_elapsed,
            },
            "round_1_claim_relevance": {
                "call_count": 1,
                "recorded_tokens": 20,
                "elapsed_seconds": worker_elapsed,
            },
            "round_1_answer_coverage": {
                "call_count": 1,
                "recorded_tokens": 20,
                "elapsed_seconds": worker_elapsed,
            },
        },
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_summarize_result_extracts_worker_metrics(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    write_result(
        path,
        quality_score=0.9,
        response_id="ollama-local",
        worker_elapsed=0.5,
    )

    summary = summarize_result(
        provider="local",
        result_path=path,
    )

    assert summary.quality_score == pytest.approx(0.9)
    assert summary.worker_metrics.call_count == 3
    assert summary.worker_metrics.recorded_tokens == 60
    assert summary.worker_metrics.elapsed_seconds == pytest.approx(1.5)
    assert summary.ollama_provenance_count == 3
    assert summary.answer_coverage_level == "fully_covered"


def test_compare_pair_reports_local_minus_openai(tmp_path: Path) -> None:
    openai_path = tmp_path / "openai.json"
    local_path = tmp_path / "local.json"
    write_result(
        openai_path,
        quality_score=0.8,
        response_id="openai-response",
        worker_elapsed=0.2,
    )
    write_result(
        local_path,
        quality_score=0.9,
        response_id="ollama-local",
        worker_elapsed=0.5,
    )

    comparison = compare_pair(
        openai=summarize_result(
            provider="openai",
            result_path=openai_path,
        ),
        local=summarize_result(
            provider="local",
            result_path=local_path,
        ),
    )

    assert comparison["delta_local_minus_openai"]["quality_score"] == (
        pytest.approx(0.1)
    )
    assert comparison["delta_local_minus_openai"][
        "worker_elapsed_seconds"
    ] == pytest.approx(0.9)


def test_aggregate_pairs_requires_nonempty() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        aggregate_pairs([])
