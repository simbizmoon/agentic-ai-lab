"""Tests for Ollama structured-output format payloads."""

from typing import Any

import pytest

from app.services.ollama_client import OllamaClient


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {
            "model": "qwen3.5:4b",
            "response": '{"city":"서울","temperature":24}',
            "thinking": "",
            "done": True,
            "done_reason": "stop",
            "total_duration": 100,
            "load_duration": 10,
            "prompt_eval_count": 5,
            "prompt_eval_duration": 20,
            "eval_count": 8,
            "eval_duration": 50,
        }


class CapturingHttpClient:
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


def test_generate_sends_json_format() -> None:
    http = CapturingHttpClient()
    client = OllamaClient(http_client=http)

    client.generate(
        model="qwen3.5:4b",
        prompt="test",
        think=False,
        response_format="json",
    )

    assert http.payload is not None
    assert http.payload["format"] == "json"


def test_generate_sends_schema_format() -> None:
    http = CapturingHttpClient()
    client = OllamaClient(http_client=http)
    schema = {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    }

    client.generate(
        model="qwen3.5:4b",
        prompt="test",
        think=False,
        response_format=schema,
    )

    assert http.payload is not None
    assert http.payload["format"] == schema


def test_generate_rejects_unknown_string_format() -> None:
    client = OllamaClient(http_client=CapturingHttpClient())

    with pytest.raises(
        ValueError,
        match="response_format string must be 'json'",
    ):
        client.generate(
            model="qwen3.5:4b",
            prompt="test",
            think=False,
            response_format="yaml",
        )
