"""Tests for Ollama native tool-calling chat client."""

from typing import Any

import pytest

from app.services.ollama_tool_client import (
    OllamaToolClient,
    OllamaToolResponseError,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeHttpClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> FakeResponse:
        self.calls.append(
            {"url": url, "json": json, "timeout": timeout}
        )
        return FakeResponse(self.payload)


def valid_payload() -> dict[str, Any]:
    return {
        "model": "qwen3.5:4b",
        "message": {
            "role": "assistant",
            "content": "",
            "thinking": "",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_document_statistics",
                        "arguments": {
                            "document_text": "hello world",
                        },
                    },
                }
            ],
        },
        "done": True,
        "done_reason": "stop",
        "total_duration": 100,
        "load_duration": 10,
        "prompt_eval_count": 20,
        "prompt_eval_duration": 30,
        "eval_count": 5,
        "eval_duration": 50,
    }


def test_chat_sends_native_tools_and_parses_call() -> None:
    http = FakeHttpClient(valid_payload())
    client = OllamaToolClient(http_client=http)

    result = client.chat(
        model="qwen3.5:4b",
        user_request="count this",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_document_statistics",
                    "description": "count",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    },
                },
            }
        ],
        think=False,
        temperature=0.0,
        seed=42,
    )

    assert result.tool_calls[0].name == "get_document_statistics"
    assert result.tool_calls[0].arguments == {
        "document_text": "hello world"
    }
    sent = http.calls[0]["json"]
    assert sent["tools"][0]["function"]["name"] == (
        "get_document_statistics"
    )
    assert sent["stream"] is False
    assert sent["think"] is False


def test_chat_accepts_direct_response_without_tool_calls() -> None:
    payload = valid_payload()
    payload["message"] = {
        "role": "assistant",
        "content": "No tool needed.",
        "thinking": "",
    }
    client = OllamaToolClient(
        http_client=FakeHttpClient(payload)
    )

    result = client.chat(
        model="qwen3.5:4b",
        user_request="explain tools",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "x",
                    "parameters": {"type": "object"},
                },
            }
        ],
        think=False,
    )

    assert result.tool_calls == ()
    assert result.content == "No tool needed."


def test_chat_rejects_non_object_arguments() -> None:
    payload = valid_payload()
    payload["message"]["tool_calls"][0]["function"]["arguments"] = "bad"
    client = OllamaToolClient(
        http_client=FakeHttpClient(payload)
    )

    with pytest.raises(
        OllamaToolResponseError,
        match="arguments must be an object",
    ):
        client.chat(
            model="qwen3.5:4b",
            user_request="count",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "x",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            think=False,
        )
