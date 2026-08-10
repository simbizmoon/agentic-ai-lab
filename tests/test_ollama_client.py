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

    def __init__(
        self,
        payload: object,
        *,
        status_code: int = 200,
    ) -> None:
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request(
            "POST",
            "http://127.0.0.1:11434/api/generate",
        )

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=self.request,
                response=httpx.Response(
                    self.status_code,
                    request=self.request,
                ),
            )

    def json(self) -> object:
        return self._payload


class FakeHttpClient:
    """Capture Ollama HTTP requests."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "json": dict(json),
                "timeout": timeout,
            }
        )
        return self._responses.pop(0)


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
    http_client = FakeHttpClient(
        [FakeResponse(valid_payload())]
    )
    client = OllamaClient(
        http_client=http_client,
        timeout_seconds=30.0,
    )

    result = client.generate(
        model="qwen3.5:4b",
        prompt="한국어로 답하라.",
        think=False,
        keep_alive="5m",
    )

    assert result.model == "qwen3.5:4b"
    assert result.response == "로컬 모델이 정상적으로 응답했습니다."
    assert result.generation_tokens_per_second == pytest.approx(
        86.831,
        rel=1e-3,
    )
    assert result.prompt_tokens_per_second == pytest.approx(
        303.331,
        rel=1e-3,
    )

    assert http_client.calls[0]["json"] == {
        "model": "qwen3.5:4b",
        "prompt": "한국어로 답하라.",
        "stream": False,
        "think": False,
        "keep_alive": "5m",
    }


def test_unload_uses_keep_alive_zero() -> None:
    http_client = FakeHttpClient(
        [FakeResponse({"model": "qwen3.5:4b", "done": True})]
    )
    client = OllamaClient(http_client=http_client)

    client.unload(model="qwen3.5:4b")

    assert http_client.calls[0]["json"] == {
        "model": "qwen3.5:4b",
        "keep_alive": 0,
        "stream": False,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("model", " "),
        ("prompt", ""),
    ],
)
def test_generate_rejects_blank_input(
    field: str,
    value: str,
) -> None:
    client = OllamaClient(
        http_client=FakeHttpClient(
            [FakeResponse(valid_payload())]
        )
    )
    kwargs = {
        "model": "qwen3.5:4b",
        "prompt": "prompt",
        "think": False,
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        client.generate(**kwargs)


@pytest.mark.parametrize("value", ["", "   "])
def test_generate_rejects_blank_keep_alive(
    value: str,
) -> None:
    client = OllamaClient(
        http_client=FakeHttpClient(
            [FakeResponse(valid_payload())]
        )
    )

    with pytest.raises(ValueError):
        client.generate(
            model="qwen3.5:4b",
            prompt="prompt",
            think=False,
            keep_alive=value,
        )


def test_generate_rejects_boolean_keep_alive() -> None:
    client = OllamaClient(
        http_client=FakeHttpClient(
            [FakeResponse(valid_payload())]
        )
    )

    with pytest.raises(TypeError):
        client.generate(
            model="qwen3.5:4b",
            prompt="prompt",
            think=False,
            keep_alive=True,  # type: ignore[arg-type]
        )


def test_generate_rejects_incomplete_non_streaming_response() -> None:
    payload = valid_payload()
    payload["done"] = False

    client = OllamaClient(
        http_client=FakeHttpClient(
            [FakeResponse(payload)]
        )
    )

    with pytest.raises(
        OllamaResponseError,
        match="was not complete",
    ):
        client.generate(
            model="qwen3.5:4b",
            prompt="prompt",
            think=False,
        )


def test_generate_rejects_missing_required_metric() -> None:
    payload = valid_payload()
    del payload["eval_duration"]

    client = OllamaClient(
        http_client=FakeHttpClient(
            [FakeResponse(payload)]
        )
    )

    with pytest.raises(
        OllamaResponseError,
        match="eval_duration",
    ):
        client.generate(
            model="qwen3.5:4b",
            prompt="prompt",
            think=False,
        )


def test_generate_rejects_http_error() -> None:
    client = OllamaClient(
        http_client=FakeHttpClient(
            [
                FakeResponse(
                    {"error": "failed"},
                    status_code=500,
                )
            ]
        )
    )

    with pytest.raises(OllamaTransportError):
        client.generate(
            model="qwen3.5:4b",
            prompt="prompt",
            think=False,
        )
