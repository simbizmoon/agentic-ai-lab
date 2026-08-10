"""Tests for local LLM benchmark JSON artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkMetrics,
    LocalLLMBenchmarkResult,
    LocalLLMBenchmarkStatus,
)
from app.evals.local_llm_benchmark_artifact import (
    LocalLLMBenchmarkArtifact,
    LocalLLMBenchmarkArtifactWriter,
)
from app.evals.local_llm_benchmark_summary import (
    summarize_local_llm_results,
)


def result(
    *,
    run_label: str,
    think: bool = False,
) -> LocalLLMBenchmarkResult:
    """Return one valid benchmark result."""
    return LocalLLMBenchmarkResult(
        benchmark_id=f"benchmark-{run_label}",
        run_label=run_label,
        model="qwen3.5:4b",
        think=think,
        status=LocalLLMBenchmarkStatus.SUCCEEDED,
        response="정답: C",
        thinking="사고" if think else "",
        done_reason="stop",
        quality_passed=True,
        expected_substring="정답: C",
        metrics=LocalLLMBenchmarkMetrics(
            total_duration_ns=2_000_000_000,
            load_duration_ns=500_000_000,
            prompt_eval_count=20,
            prompt_eval_duration_ns=100_000_000,
            eval_count=100,
            eval_duration_ns=1_000_000_000,
            prompt_tokens_per_second=200.0,
            generation_tokens_per_second=100.0,
        ),
    )


def test_writer_persists_results_and_summaries(tmp_path) -> None:
    off = [
        result(run_label="think-off-cold-1"),
        result(run_label="think-off-warm-1"),
    ]
    on = [
        result(run_label="think-on-cold-1", think=True),
        result(run_label="think-on-warm-1", think=True),
    ]
    artifact = LocalLLMBenchmarkArtifact(
        created_at=datetime(2026, 8, 10, tzinfo=UTC),
        model="qwen3.5:4b",
        benchmark_group="phase4a3-thinking-ab",
        results=[*off, *on],
        summaries=[
            summarize_local_llm_results(off),
            summarize_local_llm_results(on),
        ],
    )
    path = tmp_path / "result.json"

    LocalLLMBenchmarkArtifactWriter().write(
        artifact=artifact,
        path=path,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["artifact_version"] == "1.1.0"
    assert len(payload["results"]) == 4
    assert len(payload["summaries"]) == 2
    assert payload["summaries"][0]["think"] is False
    assert payload["summaries"][1]["think"] is True


def test_artifact_rejects_duplicate_run_labels() -> None:
    with pytest.raises(
        ValidationError,
        match="run labels must be unique",
    ):
        LocalLLMBenchmarkArtifact(
            created_at=datetime(2026, 8, 10, tzinfo=UTC),
            model="qwen3.5:4b",
            benchmark_group="phase4a3-thinking-ab",
            results=[
                result(run_label="duplicate"),
                result(run_label="duplicate"),
            ],
        )
