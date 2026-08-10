"""Tests for the local LLM benchmark runner."""

from __future__ import annotations

import pytest

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkRequest,
)
from app.evals.local_llm_benchmark_runner import (
    LocalLLMBenchmarkRunner,
)
from app.services.ollama_client import (
    OllamaGenerateResponse,
)


class FakeOllamaClient:
    """Return one deterministic normalized Ollama response."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        think: bool,
        stream: bool = False,
        keep_alive: str | int | None = None,
    ) -> OllamaGenerateResponse:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "think": think,
                "stream": stream,
                "keep_alive": keep_alive,
            }
        )
        return OllamaGenerateResponse(
            model=model,
            response="정상 응답",
            thinking="",
            done=True,
            done_reason="stop",
            total_duration_ns=2_000_000_000,
            load_duration_ns=500_000_000,
            prompt_eval_count=20,
            prompt_eval_duration_ns=100_000_000,
            eval_count=100,
            eval_duration_ns=1_000_000_000,
        )


def test_runner_produces_normalized_benchmark_result() -> None:
    client = FakeOllamaClient()
    runner = LocalLLMBenchmarkRunner(client=client)

    request = LocalLLMBenchmarkRequest(
        benchmark_id="local-llm-smoke-001",
        model="qwen3.5:4b",
        prompt="한국어로 한 문장으로 답하라.",
        think=False,
        run_label="phase4a1",
        keep_alive="5m",
        metadata={"category": "korean_instruction"},
    )

    result = runner.run(request)

    assert result.benchmark_id == "local-llm-smoke-001"
    assert result.run_label == "phase4a1"
    assert result.model == "qwen3.5:4b"
    assert result.think is False
    assert result.response == "정상 응답"
    assert result.metadata == {
        "category": "korean_instruction",
        "provider": "ollama",
    }

    assert result.metrics.prompt_tokens_per_second == pytest.approx(
        200.0
    )
    assert (
        result.metrics.generation_tokens_per_second
        == pytest.approx(100.0)
    )

    assert client.calls == [
        {
            "model": "qwen3.5:4b",
            "prompt": "한국어로 한 문장으로 답하라.",
            "think": False,
            "stream": False,
            "keep_alive": "5m",
        }
    ]


def test_request_rejects_blank_prompt() -> None:
    with pytest.raises(ValueError, match="prompt must not be blank"):
        LocalLLMBenchmarkRequest(
            benchmark_id="local-llm-smoke-001",
            model="qwen3.5:4b",
            prompt=" ",
            think=False,
        )


def test_result_requires_nonblank_successful_response() -> None:
    class EmptyResponseClient(FakeOllamaClient):
        def generate(
            self,
            *,
            model: str,
            prompt: str,
            think: bool,
            stream: bool = False,
            keep_alive: str | int | None = None,
        ) -> OllamaGenerateResponse:
            return OllamaGenerateResponse(
                model=model,
                response="",
                thinking="too much thinking",
                done=True,
                done_reason="length",
                total_duration_ns=10,
                load_duration_ns=1,
                prompt_eval_count=1,
                prompt_eval_duration_ns=1,
                eval_count=1,
                eval_duration_ns=1,
            )

    runner = LocalLLMBenchmarkRunner(
        client=EmptyResponseClient()
    )
    request = LocalLLMBenchmarkRequest(
        benchmark_id="local-llm-smoke-001",
        model="qwen3.5:4b",
        prompt="prompt",
        think=True,
    )

    with pytest.raises(
        ValueError,
        match="response must not be blank",
    ):
        runner.run(request)
