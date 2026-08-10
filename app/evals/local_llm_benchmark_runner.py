"""Execution service for one local LLM runtime benchmark."""

from __future__ import annotations

import re
from typing import Protocol

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkMetrics,
    LocalLLMBenchmarkRequest,
    LocalLLMBenchmarkResult,
    LocalLLMBenchmarkStatus,
)
from app.services.ollama_client import OllamaGenerateResponse

FINAL_ANSWER_PATTERN = re.compile(
    r"^\s*정답\s*:\s*(.+?)\s*$",
    flags=re.IGNORECASE,
)


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
        num_predict: int | None = None,
        temperature: float | None = None,
        seed: int | None = None,
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
            num_predict=request.num_predict,
            temperature=request.temperature,
            seed=request.seed,
        )

        response_present = bool(generated.response.strip())
        stopped_by_length = generated.done_reason == "length"
        succeeded = response_present and not stopped_by_length

        failure_reason: str | None = None
        if not succeeded:
            if stopped_by_length:
                failure_reason = "generation_stopped_by_length"
            elif not response_present:
                failure_reason = "empty_final_response"
            else:
                failure_reason = "generation_failed"

        parsed_answer = self._parse_final_answer(
            generated.response
        )
        quality_passed: bool | None = None

        if request.expected_answer is not None:
            quality_passed = (
                parsed_answer is not None
                and parsed_answer.casefold()
                == request.expected_answer.strip().casefold()
            )
        elif request.expected_substring is not None:
            quality_passed = (
                request.expected_substring.casefold()
                in generated.response.casefold()
            )

        return LocalLLMBenchmarkResult(
            benchmark_id=request.benchmark_id,
            run_label=request.run_label,
            model=generated.model,
            think=request.think,
            status=(
                LocalLLMBenchmarkStatus.SUCCEEDED
                if succeeded
                else LocalLLMBenchmarkStatus.FAILED
            ),
            response=generated.response,
            thinking=generated.thinking,
            done_reason=generated.done_reason,
            failure_reason=failure_reason,
            quality_passed=quality_passed,
            expected_substring=request.expected_substring,
            expected_answer=request.expected_answer,
            parsed_answer=parsed_answer,
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

    @staticmethod
    def _parse_final_answer(response: str) -> str | None:
        """Parse only the last nonblank `정답: ...` line."""
        lines = [
            line.strip()
            for line in response.splitlines()
            if line.strip()
        ]
        if not lines:
            return None

        match = FINAL_ANSWER_PATTERN.fullmatch(lines[-1])
        if match is None:
            return None
        return match.group(1).strip()
