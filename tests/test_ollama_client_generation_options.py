"""Tests for bounded reproducible Ollama generation options."""

from __future__ import annotations

from typing import Any

from app.services.ollama_client import OllamaClient


class FakeResponse:
    """Return one valid Ollama response."""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "model": "qwen3.5:4b",
            "response": "정답: 8",
            "thinking": "",
            "done": True,
            "done_reason": "stop",
            "total_duration": 1,
            "load_duration": 1,
            "prompt_eval_count": 1,
            "prompt_eval_duration": 1,
            "eval_count": 1,
            "eval_duration": 1,
        }


class FakeHttpClient:
    """Capture the request body."""

    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> FakeResponse:
        self.payload = json
        return FakeResponse()


def test_generate_sends_reproducible_generation_options() -> None:
    http_client = FakeHttpClient()
    client = OllamaClient(http_client=http_client)

    client.generate(
        model="qwen3.5:4b",
        prompt="문제",
        think=True,
        keep_alive="5m",
        num_predict=1024,
        temperature=0.0,
        seed=42,
    )

    assert http_client.payload == {
        "model": "qwen3.5:4b",
        "prompt": "문제",
        "stream": False,
        "think": True,
        "keep_alive": "5m",
        "options": {
            "num_predict": 1024,
            "temperature": 0.0,
            "seed": 42,
        },
    }
