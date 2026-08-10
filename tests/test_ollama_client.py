"""Tests for the minimal Ollama HTTP client."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.services.ollama_client import (
    OllamaClient,
    OllamaResponseError,
    OllamaTransportError,
)


class FakeResponse:
    """Controlled HTTP response for Ollama client tests."""

    def __init__(self, payload: object, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("POST", "http://127.0.0.1:11434/api/generate")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self) -> object:
        return self._payload


class FakeHttpClient:
    """Capture one Ollama HTTP request."""

    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> FakeResponse:
        self.calls.append({"url": url, "json": dict(json), "timeout": timeout})
        return self._response


def valid_payload() -> dict[str, object]:
    """Return one valid non-streaming Ollama payload."""
    return {
        "model": "qwen3.5:4b",
        "response": "로컬 모델이 정상적으로 응답했습니다.",
        "thinking": "",
        "done": True,
        "done_reason": "stop",
        "total_duration": 11_435_096_902,
        "load_duration": 10_055_406_807,
        "prompt_eval_count": 30,
        "prompt_eval_duration": 98_902_000,
        "eval_count": 111,
        "eval_duration": 1_278_330_000,
    }


def test_generate_sends_expected_request_and_parses_metrics() -> None:
    response = FakeResponse(valid_payload())
    http_client = FakeHttpClient(response)
    client = OllamaClient(http_client=http_client, timeout_seconds=30.0)
    result = client.generate(
        model="qwen3.5:4b",
        prompt="한국어로 답하라.",
        think=False,
    )
    assert result.model == "qwen3.5:4b"
    assert result.response == "로컬 모델이 정상적으로 응답했습니다."
    assert result.thinking == ""
    assert result.done is True
    assert result.done_reason == "stop"
    assert result.total_duration_ns == 11_435_096_902
    assert result.eval_count == 111
    assert result.generation_tokens_per_second == pytest.approx(86.831, rel=1e-3)
    assert result.prompt_tokens_per_second == pytest.approx(303.331, rel=1e-3)
    assert http_client.calls == [{
        "url": "http://127.0.0.1:11434/api/generate",
        "json": {
            "model": "qwen3.5:4b",
            "prompt": "한국어로 답하라.",
            "stream": False,
            "think": False,
        },
        "timeout": 30.0,
    }]


@pytest.mark.parametrize(("field", "value"), [("model", " "), ("prompt", "")])
def test_generate_rejects_blank_input(field: str, value: str) -> None:
    client = OllamaClient(http_client=FakeHttpClient(FakeResponse(valid_payload())))
    kwargs: dict[str, object] = {
        "model": "qwen3.5:4b",
        "prompt": "prompt",
        "think": False,
    }
    kwargs[field] = value
    with pytest.raises(ValueError):
        client.generate(**kwargs)  # type: ignore[arg-type]


def test_generate_rejects_incomplete_non_streaming_response() -> None:
    payload = valid_payload()
    payload["done"] = False
    client = OllamaClient(http_client=FakeHttpClient(FakeResponse(payload)))
    with pytest.raises(OllamaResponseError, match="was not complete"):
        client.generate(model="qwen3.5:4b", prompt="prompt", think=False)


def test_generate_rejects_missing_required_metric() -> None:
    payload = valid_payload()
    del payload["eval_duration"]
    client = OllamaClient(http_client=FakeHttpClient(FakeResponse(payload)))
    with pytest.raises(OllamaResponseError, match="eval_duration"):
        client.generate(model="qwen3.5:4b", prompt="prompt", think=False)


def test_generate_rejects_http_error() -> None:
    client = OllamaClient(
        http_client=FakeHttpClient(FakeResponse({"error": "failed"}, status_code=500))
    )
    with pytest.raises(OllamaTransportError):
        client.generate(model="qwen3.5:4b", prompt="prompt", think=False)
