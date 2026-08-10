"""Schemas for Korean instruction-following benchmark summaries."""

from __future__ import annotations

from dataclasses import dataclass

from app.evals.local_llm_benchmark import LocalLLMBenchmarkResult


@dataclass(frozen=True)
class KoreanInstructionBenchmarkCaseResult:
    """One scored Korean instruction benchmark run."""

    case_id: str
    case_name: str
    repetition: int
    benchmark_result: LocalLLMBenchmarkResult
    instruction_passed: bool
    checks_passed: int
    checks_total: int
    failures: tuple[str, ...]


@dataclass(frozen=True)
class KoreanInstructionBenchmarkSummary:
    """Aggregate Korean instruction-following benchmark result."""

    model: str
    run_count: int
    case_count: int
    passed_runs: int
    pass_rate: float
    check_count: int
    passed_checks: int
    check_pass_rate: float
    mean_total_duration_ms: float
    mean_eval_tokens: float


def summarize_korean_instruction_results(
    *,
    model: str,
    case_count: int,
    results: list[KoreanInstructionBenchmarkCaseResult],
) -> KoreanInstructionBenchmarkSummary:
    """Summarize deterministic instruction-following outcomes."""
    if not results:
        raise ValueError("results must not be empty")

    run_count = len(results)
    passed_runs = sum(result.instruction_passed for result in results)
    check_count = sum(result.checks_total for result in results)
    passed_checks = sum(result.checks_passed for result in results)

    return KoreanInstructionBenchmarkSummary(
        model=model,
        run_count=run_count,
        case_count=case_count,
        passed_runs=passed_runs,
        pass_rate=passed_runs / run_count,
        check_count=check_count,
        passed_checks=passed_checks,
        check_pass_rate=(
            passed_checks / check_count
            if check_count
            else 0.0
        ),
        mean_total_duration_ms=(
            sum(
                result.benchmark_result.metrics.total_duration_ns
                for result in results
            )
            / run_count
            / 1_000_000
        ),
        mean_eval_tokens=(
            sum(
                result.benchmark_result.metrics.eval_count
                for result in results
            )
            / run_count
        ),
    )
