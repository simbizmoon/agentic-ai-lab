"""Tests for the local LLM benchmark runner."""

from __future__ import annotations

import pytest

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkRequest,
    LocalLLMBenchmarkStatus,
)
from app.evals.local_llm_benchmark_runner import (
    LocalLLMBenchmarkRunner,
)
from app.services.ollama_client import (
    OllamaGenerateResponse,
)


class FakeOllamaClient:
    """Return one deterministic normalized Ollama response."""

    def __init__(
        self,
        *,
        response: str = "정답: C",
        thinking: str = "",
        done_reason: str | None = "stop",
    ) -> None:
        self._response = response
        self._thinking = thinking
        self._done_reason = done_reason
        self.calls: list[dict[str, object]] = []

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
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "think": think,
                "stream": stream,
                "keep_alive": keep_alive,
                "num_predict": num_predict,
                "temperature": temperature,
                "seed": seed,
            }
        )
        return OllamaGenerateResponse(
            model=model,
            response=self._response,
            thinking=self._thinking,
            done=True,
            done_reason=self._done_reason,
            total_duration_ns=2_000_000_000,
            load_duration_ns=500_000_000,
            prompt_eval_count=20,
            prompt_eval_duration_ns=100_000_000,
            eval_count=100,
            eval_duration_ns=1_000_000_000,
        )


def substring_request(
    *,
    think: bool = False,
) -> LocalLLMBenchmarkRequest:
    """Return one backward-compatible substring benchmark request."""
    return LocalLLMBenchmarkRequest(
        benchmark_id="local-llm-smoke-001",
        model="qwen3.5:4b",
        prompt="문제를 풀어라.",
        think=think,
        run_label="phase4a3",
        keep_alive="5m",
        expected_substring="정답: C",
        metadata={"category": "thinking_ab"},
    )


def test_runner_produces_successful_substring_result() -> None:
    client = FakeOllamaClient()
    runner = LocalLLMBenchmarkRunner(client=client)

    result = runner.run(substring_request())

    assert result.status is LocalLLMBenchmarkStatus.SUCCEEDED
    assert result.quality_passed is True
    assert result.response == "정답: C"
    assert result.failure_reason is None
    assert result.response_char_count == len("정답: C")
    assert result.thinking_char_count == 0


def test_runner_records_wrong_substring_without_runtime_failure() -> None:
    runner = LocalLLMBenchmarkRunner(
        client=FakeOllamaClient(response="정답: A")
    )

    result = runner.run(substring_request())

    assert result.status is LocalLLMBenchmarkStatus.SUCCEEDED
    assert result.quality_passed is False


def test_runner_records_length_failure_instead_of_raising() -> None:
    runner = LocalLLMBenchmarkRunner(
        client=FakeOllamaClient(
            response="",
            thinking="긴 사고 과정",
            done_reason="length",
        )
    )

    result = runner.run(substring_request(think=True))

    assert result.status is LocalLLMBenchmarkStatus.FAILED
    assert result.quality_passed is False
    assert result.failure_reason == "generation_stopped_by_length"
    assert result.response == ""
    assert result.thinking == "긴 사고 과정"


def test_request_rejects_blank_prompt() -> None:
    with pytest.raises(ValueError, match="prompt must not be blank"):
        LocalLLMBenchmarkRequest(
            benchmark_id="local-llm-smoke-001",
            model="qwen3.5:4b",
            prompt=" ",
            think=False,
        )
