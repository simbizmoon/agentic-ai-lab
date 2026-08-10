"""Execution service for one local LLM runtime benchmark."""

from __future__ import annotations

from typing import Protocol

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkMetrics,
    LocalLLMBenchmarkRequest,
    LocalLLMBenchmarkResult,
)
from app.services.ollama_client import OllamaGenerateResponse


class LocalLLMGenerateClient(Protocol):
    """Provider subset required by LocalLLMBenchmarkRunner."""

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        think: bool,
        stream: bool = False,
        keep_alive: str | int | None = None,
    ) -> OllamaGenerateResponse:
        """Generate one normalized local-model response."""


class LocalLLMBenchmarkRunner:
    """Run one benchmark request through an injected local LLM client."""

    def __init__(
        self,
        *,
        client: LocalLLMGenerateClient,
    ) -> None:
        self._client = client

    def run(
        self,
        request: LocalLLMBenchmarkRequest,
    ) -> LocalLLMBenchmarkResult:
        """Execute one benchmark and normalize runtime metrics."""
        generated = self._client.generate(
            model=request.model,
            prompt=request.prompt,
            think=request.think,
            stream=False,
            keep_alive=request.keep_alive,
        )

        return LocalLLMBenchmarkResult(
            benchmark_id=request.benchmark_id,
            run_label=request.run_label,
            model=generated.model,
            think=request.think,
            response=generated.response,
            thinking=generated.thinking,
            done_reason=generated.done_reason,
            metrics=LocalLLMBenchmarkMetrics(
                total_duration_ns=generated.total_duration_ns,
                load_duration_ns=generated.load_duration_ns,
                prompt_eval_count=generated.prompt_eval_count,
                prompt_eval_duration_ns=(
                    generated.prompt_eval_duration_ns
                ),
                eval_count=generated.eval_count,
                eval_duration_ns=generated.eval_duration_ns,
                prompt_tokens_per_second=(
                    generated.prompt_tokens_per_second
                ),
                generation_tokens_per_second=(
                    generated.generation_tokens_per_second
                ),
            ),
            metadata={
                **request.metadata,
                "provider": "ollama",
            },
        )
