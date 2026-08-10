"""Tests for local LLM repeated-run benchmark summaries."""

from __future__ import annotations

import pytest

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkMetrics,
    LocalLLMBenchmarkResult,
    LocalLLMBenchmarkStatus,
)
from app.evals.local_llm_benchmark_summary import (
    summarize_local_llm_results,
)


def result(
    *,
    run_label: str,
    total_ms: int,
    quality_passed: bool,
) -> LocalLLMBenchmarkResult:
    """Return one repeated benchmark result."""
    return LocalLLMBenchmarkResult(
        benchmark_id=f"benchmark-{run_label}",
        run_label=run_label,
        model="qwen3.5:4b",
        think=False,
        status=LocalLLMBenchmarkStatus.SUCCEEDED,
        response="정답: C",
        thinking="",
        done_reason="stop",
        quality_passed=quality_passed,
        expected_substring="정답: C",
        metrics=LocalLLMBenchmarkMetrics(
            total_duration_ns=total_ms * 1_000_000,
            load_duration_ns=100_000_000,
            prompt_eval_count=20,
            prompt_eval_duration_ns=100_000_000,
            eval_count=100,
            eval_duration_ns=1_000_000_000,
            prompt_tokens_per_second=200.0,
            generation_tokens_per_second=100.0,
        ),
    )


def test_summary_aggregates_repeated_results() -> None:
    summary = summarize_local_llm_results(
        [
            result(
                run_label="run-1",
                total_ms=1000,
                quality_passed=True,
            ),
            result(
                run_label="run-2",
                total_ms=2000,
                quality_passed=False,
            ),
            result(
                run_label="run-3",
                total_ms=3000,
                quality_passed=True,
            ),
        ]
    )

    assert summary.run_count == 3
    assert summary.success_count == 3
    assert summary.failure_count == 0
    assert summary.quality_pass_count == 2
    assert summary.mean_total_duration_ms == pytest.approx(2000)
    assert summary.median_total_duration_ms == pytest.approx(2000)
    assert summary.min_total_duration_ms == pytest.approx(1000)
    assert summary.max_total_duration_ms == pytest.approx(3000)
    assert summary.mean_generation_tokens_per_second == pytest.approx(
        100.0
    )


def test_summary_rejects_mixed_think_modes() -> None:
    first = result(
        run_label="run-1",
        total_ms=1000,
        quality_passed=True,
    )
    second_data = result(
        run_label="run-2",
        total_ms=1000,
        quality_passed=True,
    ).model_dump(mode="python")
    second_data["think"] = True
    second = LocalLLMBenchmarkResult.model_validate(second_data)

    with pytest.raises(
        ValueError,
        match="same think mode",
    ):
        summarize_local_llm_results([first, second])
