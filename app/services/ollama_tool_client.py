"""Minimal Ollama /api/chat client for native tool-calling benchmarks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class OllamaToolClientError(RuntimeError):
    """Base native tool-calling client error."""


class OllamaToolTransportError(OllamaToolClientError):
    """Raised when Ollama chat transport fails."""


class OllamaToolResponseError(OllamaToolClientError):
    """Raised when Ollama returns an invalid chat response."""


class OllamaToolHttpClient(Protocol):
    """HTTP subset required by the Ollama native tool client."""

    def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        timeout: float,
    ) -> Any:
        """Send one JSON POST request."""


@dataclass(frozen=True)
class OllamaNativeToolCall:
    """One normalized Ollama native function call."""

    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class OllamaToolChatResponse:
    """Normalized non-streaming Ollama chat response."""

    model: str
    content: str
    thinking: str
    tool_calls: tuple[OllamaNativeToolCall, ...]
    done_reason: str | None
    total_duration_ns: int
    load_duration_ns: int
    prompt_eval_count: int
    prompt_eval_duration_ns: int
    eval_count: int
    eval_duration_ns: int

    @property
    def total_duration_seconds(self) -> float:
        return self.total_duration_ns / 1_000_000_000

    @property
    def generation_tokens_per_second(self) -> float | None:
        seconds = self.eval_duration_ns / 1_000_000_000
        if self.eval_count == 0 or seconds <= 0:
            return None
        return self.eval_count / seconds


class OllamaToolClient:
    """Call Ollama /api/chat with native tool schemas."""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
        http_client: OllamaToolHttpClient | None = None,
    ) -> None:
        cleaned = base_url.strip().rstrip("/")
        if not cleaned:
            raise ValueError("base_url must not be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._base_url = cleaned
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client

    def chat(
        self,
        *,
        model: str,
        user_request: str,
        tools: list[dict[str, Any]],
        think: bool,
        keep_alive: str | int | None = None,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> OllamaToolChatResponse:
        """Run one non-streaming native tool-selection chat turn."""
        cleaned_model = model.strip()
        cleaned_request = user_request.strip()
        if not cleaned_model:
            raise ValueError("model must not be blank")
        if not cleaned_request:
            raise ValueError("user_request must not be blank")
        if not tools:
            raise ValueError("tools must not be empty")

        payload: dict[str, Any] = {
            "model": cleaned_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are AIRA, a document research assistant. "
                        "Use get_document_statistics for exact character, "
                        "word, or line counts. Use extract_document_keywords "
                        "for frequent document keywords. Do not estimate tool "
                        "results yourself. Choose at most one tool. If the "
                        "request needs both tools, call no tool."
                    ),
                },
                {
                    "role": "user",
                    "content": cleaned_request,
                },
            ],
            "tools": tools,
            "stream": False,
            "think": think,
        }

        if keep_alive is not None:
            if isinstance(keep_alive, bool):
                raise TypeError("keep_alive must be a string or integer")
            if isinstance(keep_alive, str) and not keep_alive.strip():
                raise ValueError("keep_alive must not be blank")
            payload["keep_alive"] = keep_alive

        options: dict[str, Any] = {}
        if temperature is not None:
            if isinstance(temperature, bool):
                raise TypeError("temperature must be numeric")
            if temperature < 0:
                raise ValueError("temperature must be nonnegative")
            options["temperature"] = temperature
        if seed is not None:
            if isinstance(seed, bool):
                raise TypeError("seed must be an integer")
            options["seed"] = seed
        if options:
            payload["options"] = options

        response = self._post(payload)
        return self._parse(response)

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=self._timeout_seconds,
                )
            else:
                response = httpx.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                    timeout=self._timeout_seconds,
                )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise OllamaToolTransportError(
                "Ollama chat request failed"
            ) from error

        try:
            data = response.json()
        except ValueError as error:
            raise OllamaToolResponseError(
                "Ollama chat response was not valid JSON"
            ) from error

        if not isinstance(data, dict):
            raise OllamaToolResponseError(
                "Ollama chat response must be an object"
            )
        return data

    @staticmethod
    def _parse(data: dict[str, Any]) -> OllamaToolChatResponse:
        message = data.get("message")
        if not isinstance(message, dict):
            raise OllamaToolResponseError(
                "Ollama chat response is missing message"
            )

        model = data.get("model")
        if not isinstance(model, str) or not model.strip():
            raise OllamaToolResponseError("invalid model")

        content = message.get("content", "")
        thinking = message.get("thinking", "")
        if not isinstance(content, str):
            raise OllamaToolResponseError("message content must be a string")
        if not isinstance(thinking, str):
            raise OllamaToolResponseError(
                "message thinking must be a string"
            )

        raw_calls = message.get("tool_calls", [])
        if raw_calls is None:
            raw_calls = []
        if not isinstance(raw_calls, list):
            raise OllamaToolResponseError(
                "message tool_calls must be a list"
            )

        normalized_calls: list[OllamaNativeToolCall] = []
        for raw_call in raw_calls:
            if not isinstance(raw_call, dict):
                raise OllamaToolResponseError(
                    "tool call must be an object"
                )
            function = raw_call.get("function")
            if not isinstance(function, dict):
                raise OllamaToolResponseError(
                    "tool call function must be an object"
                )
            name = function.get("name")
            arguments = function.get("arguments")
            if not isinstance(name, str) or not name.strip():
                raise OllamaToolResponseError(
                    "tool call function name is invalid"
                )
            if not isinstance(arguments, dict):
                raise OllamaToolResponseError(
                    "tool call arguments must be an object"
                )
            normalized_calls.append(
                OllamaNativeToolCall(
                    name=name,
                    arguments=arguments,
                )
            )

        def metric(name: str) -> int:
            value = data.get(name)
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise OllamaToolResponseError(
                    f"{name} must be a nonnegative integer"
                )
            return value

        done = data.get("done")
        if done is not True:
            raise OllamaToolResponseError(
                "Ollama chat response was not complete"
            )

        done_reason = data.get("done_reason")
        if done_reason is not None and (
            not isinstance(done_reason, str)
            or not done_reason.strip()
        ):
            raise OllamaToolResponseError("invalid done_reason")

        return OllamaToolChatResponse(
            model=model,
            content=content,
            thinking=thinking,
            tool_calls=tuple(normalized_calls),
            done_reason=done_reason,
            total_duration_ns=metric("total_duration"),
            load_duration_ns=metric("load_duration"),
            prompt_eval_count=metric("prompt_eval_count"),
            prompt_eval_duration_ns=metric("prompt_eval_duration"),
            eval_count=metric("eval_count"),
            eval_duration_ns=metric("eval_duration"),
        )
