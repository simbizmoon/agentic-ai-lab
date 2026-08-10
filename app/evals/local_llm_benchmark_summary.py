"""Aggregate statistics for repeated local LLM benchmark runs."""

from __future__ import annotations

from statistics import mean, median

from pydantic import BaseModel, ConfigDict, Field

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkResult,
    LocalLLMBenchmarkStatus,
)


class LocalLLMBenchmarkSummary(BaseModel):
    """Aggregate statistics for one benchmark mode."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    model: str
    think: bool
    run_count: int = Field(ge=1)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    quality_pass_count: int | None = Field(default=None, ge=0)
    mean_total_duration_ms: float = Field(ge=0)
    median_total_duration_ms: float = Field(ge=0)
    min_total_duration_ms: float = Field(ge=0)
    max_total_duration_ms: float = Field(ge=0)
    mean_load_duration_ms: float = Field(ge=0)
    mean_generation_tokens_per_second: float | None = Field(
        default=None,
        ge=0,
    )
    mean_prompt_tokens_per_second: float | None = Field(
        default=None,
        ge=0,
    )
    mean_eval_count: float = Field(ge=0)
    mean_response_char_count: float = Field(ge=0)
    mean_thinking_char_count: float = Field(ge=0)


def summarize_local_llm_results(
    results: list[LocalLLMBenchmarkResult],
) -> LocalLLMBenchmarkSummary:
    """Summarize repeated results for one model and thinking mode."""
    if not results:
        raise ValueError("results must not be empty")

    model = results[0].model
    think = results[0].think

    if any(result.model != model for result in results):
        raise ValueError("all results must use the same model")
    if any(result.think != think for result in results):
        raise ValueError("all results must use the same think mode")

    total_ms = [
        result.metrics.total_duration_ns / 1_000_000
        for result in results
    ]
    load_ms = [
        result.metrics.load_duration_ns / 1_000_000
        for result in results
    ]
    generation_tps = [
        value
        for result in results
        if (
            value := result.metrics.generation_tokens_per_second
        )
        is not None
    ]
    prompt_tps = [
        value
        for result in results
        if (
            value := result.metrics.prompt_tokens_per_second
        )
        is not None
    ]
    quality_values = [
        result.quality_passed
        for result in results
        if result.quality_passed is not None
    ]

    success_count = sum(
        result.status is LocalLLMBenchmarkStatus.SUCCEEDED
        for result in results
    )

    return LocalLLMBenchmarkSummary(
        model=model,
        think=think,
        run_count=len(results),
        success_count=success_count,
        failure_count=len(results) - success_count,
        quality_pass_count=(
            sum(quality_values)
            if quality_values
            else None
        ),
        mean_total_duration_ms=mean(total_ms),
        median_total_duration_ms=median(total_ms),
        min_total_duration_ms=min(total_ms),
        max_total_duration_ms=max(total_ms),
        mean_load_duration_ms=mean(load_ms),
        mean_generation_tokens_per_second=(
            mean(generation_tps)
            if generation_tps
            else None
        ),
        mean_prompt_tokens_per_second=(
            mean(prompt_tps)
            if prompt_tps
            else None
        ),
        mean_eval_count=mean(
            result.metrics.eval_count for result in results
        ),
        mean_response_char_count=mean(
            result.response_char_count for result in results
        ),
        mean_thinking_char_count=mean(
            result.thinking_char_count for result in results
        ),
    )
