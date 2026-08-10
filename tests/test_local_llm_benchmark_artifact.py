"""Tests for local LLM benchmark JSON artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkMetrics,
    LocalLLMBenchmarkResult,
)
from app.evals.local_llm_benchmark_artifact import (
    LocalLLMBenchmarkArtifact,
    LocalLLMBenchmarkArtifactWriter,
)


def result(*, run_label: str) -> LocalLLMBenchmarkResult:
    """Return one valid benchmark result."""
    return LocalLLMBenchmarkResult(
        benchmark_id=f"benchmark-{run_label}",
        run_label=run_label,
        model="qwen3.5:4b",
        think=False,
        response="정상 응답",
        thinking="",
        done_reason="stop",
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


def test_writer_persists_utf8_json(tmp_path) -> None:
    artifact = LocalLLMBenchmarkArtifact(
        created_at=datetime(2026, 8, 10, tzinfo=UTC),
        model="qwen3.5:4b",
        benchmark_group="phase4a2-cold-warm",
        results=[
            result(run_label="cold"),
            result(run_label="warm"),
        ],
    )
    path = tmp_path / "result.json"

    written = LocalLLMBenchmarkArtifactWriter().write(
        artifact=artifact,
        path=path,
    )

    assert written == path
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["model"] == "qwen3.5:4b"
    assert payload["results"][0]["response"] == "정상 응답"
    assert [item["run_label"] for item in payload["results"]] == [
        "cold",
        "warm",
    ]


def test_artifact_rejects_duplicate_run_labels() -> None:
    with pytest.raises(
        ValidationError,
        match="run labels must be unique",
    ):
        LocalLLMBenchmarkArtifact(
            created_at=datetime(2026, 8, 10, tzinfo=UTC),
            model="qwen3.5:4b",
            benchmark_group="phase4a2-cold-warm",
            results=[
                result(run_label="cold"),
                result(run_label="cold"),
            ],
        )
