"""Tests for Korean instruction benchmark summary."""

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkMetrics,
    LocalLLMBenchmarkResult,
    LocalLLMBenchmarkStatus,
)
from app.evals.local_llm_korean_instruction_benchmark import (
    KoreanInstructionBenchmarkCaseResult,
    summarize_korean_instruction_results,
)


def benchmark_result(
    *,
    response: str,
    duration_ns: int,
    eval_count: int,
) -> LocalLLMBenchmarkResult:
    return LocalLLMBenchmarkResult(
        benchmark_id="phase5b1-test",
        run_label="test",
        model="qwen3.5:4b",
        think=False,
        status=LocalLLMBenchmarkStatus.SUCCEEDED,
        response=response,
        thinking="",
        done_reason="stop",
        metrics=LocalLLMBenchmarkMetrics(
            total_duration_ns=duration_ns,
            load_duration_ns=0,
            prompt_eval_count=10,
            prompt_eval_duration_ns=10_000_000,
            eval_count=eval_count,
            eval_duration_ns=100_000_000,
            prompt_tokens_per_second=1000.0,
            generation_tokens_per_second=100.0,
        ),
    )


def test_summary_counts_runs_checks_and_means() -> None:
    results = [
        KoreanInstructionBenchmarkCaseResult(
            case_id="a",
            case_name="A",
            repetition=1,
            benchmark_result=benchmark_result(
                response="ok",
                duration_ns=1_000_000_000,
                eval_count=10,
            ),
            instruction_passed=True,
            checks_passed=2,
            checks_total=2,
            failures=(),
        ),
        KoreanInstructionBenchmarkCaseResult(
            case_id="b",
            case_name="B",
            repetition=1,
            benchmark_result=benchmark_result(
                response="bad",
                duration_ns=3_000_000_000,
                eval_count=30,
            ),
            instruction_passed=False,
            checks_passed=1,
            checks_total=2,
            failures=("wrong",),
        ),
    ]

    summary = summarize_korean_instruction_results(
        model="qwen3.5:4b",
        case_count=2,
        results=results,
    )

    assert summary.run_count == 2
    assert summary.passed_runs == 1
    assert summary.pass_rate == 0.5
    assert summary.check_count == 4
    assert summary.passed_checks == 3
    assert summary.check_pass_rate == 0.75
    assert summary.mean_total_duration_ms == 2000.0
    assert summary.mean_eval_tokens == 20.0
