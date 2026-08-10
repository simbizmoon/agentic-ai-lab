"""Tests for exact-answer reasoning benchmark scoring."""

from app.evals.local_llm_benchmark import (
    LocalLLMBenchmarkRequest,
    LocalLLMBenchmarkStatus,
)
from app.evals.local_llm_benchmark_runner import (
    LocalLLMBenchmarkRunner,
)
from app.services.ollama_client import OllamaGenerateResponse


class FakeClient:
    """Return one controlled final response."""

    def __init__(self, response: str) -> None:
        self._response = response

    def generate(self, **kwargs: object) -> OllamaGenerateResponse:
        return OllamaGenerateResponse(
            model=str(kwargs["model"]),
            response=self._response,
            thinking="",
            done=True,
            done_reason="stop",
            total_duration_ns=1_000_000_000,
            load_duration_ns=100_000_000,
            prompt_eval_count=20,
            prompt_eval_duration_ns=100_000_000,
            eval_count=50,
            eval_duration_ns=500_000_000,
        )


def request() -> LocalLLMBenchmarkRequest:
    """Return one exact-answer request."""
    return LocalLLMBenchmarkRequest(
        benchmark_id="reasoning-001",
        model="qwen3.5:4b",
        prompt="문제를 풀고 마지막 줄에 정답 형식을 사용하라.",
        think=False,
        expected_answer="643",
        num_predict=1024,
        temperature=0.0,
        seed=42,
    )


def test_exact_final_answer_passes() -> None:
    result = LocalLLMBenchmarkRunner(
        client=FakeClient("설명\n정답: 643")
    ).run(request())

    assert result.status is LocalLLMBenchmarkStatus.SUCCEEDED
    assert result.parsed_answer == "643"
    assert result.quality_passed is True


def test_wrong_final_answer_fails_quality() -> None:
    result = LocalLLMBenchmarkRunner(
        client=FakeClient("설명\n정답: 634")
    ).run(request())

    assert result.status is LocalLLMBenchmarkStatus.SUCCEEDED
    assert result.parsed_answer == "634"
    assert result.quality_passed is False


def test_answer_mentioned_in_body_does_not_pass_parser() -> None:
    result = LocalLLMBenchmarkRunner(
        client=FakeClient(
            "643이 후보이지만 마지막 형식을 지키지 않았다."
        )
    ).run(request())

    assert result.parsed_answer is None
    assert result.quality_passed is False
